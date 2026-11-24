"""The running assistant: questions, feedback, the knowledge-gap queue,
settings, permission changes and the audit log. Everything a Slack handler
or the admin console does goes through here, so the rules live in one place.
"""
import copy

from . import answer, corpus, engine


class Denied(Exception):
    pass


GAP_FLOW = {
    "open": {"assign", "dismiss"},
    "assigned": {"answer", "assign", "dismiss"},
    "answered": {"publish", "assign"},
    "published": set(),
    "dismissed": {"reopen"},
}


class Workspace:
    def __init__(self, settings=None, docs=None):
        self.settings = {**engine.DEFAULTS, "log_question_text": True, **(settings or {})}
        self.index = engine.Index(copy.deepcopy(docs if docs is not None else corpus.DOCS))
        self.users = corpus.USERS
        self.channels = corpus.CHANNELS
        self.messages = []
        self.gaps = []
        self.reviews = []
        self.audit = []
        self.clock = 0
        for d in self.index.docs.values():
            if d["review_by"] < corpus.NOW and not d.get("superseded_by"):
                self.reviews.append({"doc": d["id"], "owner": d["owner"], "reason": f"review date {d['review_by']} has passed", "state": "open"})

    # helpers -----------------------------------------------------------
    def tick(self):
        self.clock += 1
        return self.clock

    def log(self, actor, action, detail):
        self.audit.append({"seq": self.tick(), "actor": actor, "action": action, **detail})

    def is_admin(self, user):
        return user in corpus.ADMINS

    # questions ---------------------------------------------------------
    def ask(self, asker, question, channel=None, case_id=None):
        if channel and asker not in self.channels[channel]["members"]:
            raise Denied(f"{asker} is not in #{channel}")
        r = engine.ask(self.index, question, asker, channel, self.settings, self.users, self.channels)
        r = answer.compose(self.index, r, question, case_id)
        msg = {"id": f"M-{len(self.messages) + 1:03d}", "asker": asker, "channel": channel, "question": question, **r,
               "feedback": []}
        self.messages.append(msg)
        if r["decision"] == "unknown":
            self.gaps.append({"id": f"G-{len(self.gaps) + 1:02d}", "question": question, "asker": asker,
                              "channel": channel, "owner": r["owner"], "state": "open", "kind": "no answer",
                              "history": [("open", asker)]})
        withheld = sum(1 for d in self.index.docs if not engine.can_read(self.index, self.users[asker]["groups"], d))
        self.log(asker, "question", {
            "message": msg["id"], "decision": r["decision"], "visibility": r["visibility"],
            "docs": sorted({c.split("#")[0] for c in r.get("chunks", [])}),
            "withheld_docs": withheld,
            "question": question if self.settings["log_question_text"] else "(not stored)",
            "draft": (r.get("draft") or {}).get("status"),
        })
        return msg

    def feedback(self, message_id, user, kind):
        msg = next(m for m in self.messages if m["id"] == message_id)
        if kind not in ("helpful", "not_helpful", "outdated"):
            raise ValueError(kind)
        msg["feedback"].append((user, kind))
        if kind == "not_helpful":
            self.gaps.append({"id": f"G-{len(self.gaps) + 1:02d}", "question": msg["question"], "asker": user,
                              "channel": msg["channel"], "owner": msg.get("owner") or "ruth", "state": "open",
                              "kind": "answer not helpful", "history": [("open", user)]})
        if kind == "outdated" and msg.get("doc"):
            doc = self.index.docs[msg["doc"]]
            self.reviews.append({"doc": doc["id"], "owner": doc["owner"], "reason": f"flagged outdated by {user}", "state": "open"})
        self.log(user, "feedback", {"message": message_id, "kind": kind})

    # gap queue ---------------------------------------------------------
    def gap(self, gap_id):
        return next(g for g in self.gaps if g["id"] == gap_id)

    def move(self, gap_id, actor, action, **kw):
        g = self.gap(gap_id)
        if action not in GAP_FLOW[g["state"]]:
            raise Denied(f"cannot {action} a gap that is {g['state']}")
        owner_or_admin = actor == g["owner"] or self.is_admin(actor)
        if action in ("assign", "dismiss", "reopen") and not self.is_admin(actor):
            raise Denied("only a knowledge admin can do that")
        if action in ("answer", "publish") and not owner_or_admin:
            raise Denied("only the owner or a knowledge admin can do that")
        if action == "assign":
            g["owner"] = kw["to"]
            g["state"] = "assigned"
        elif action == "answer":
            if not kw.get("text", "").strip():
                raise ValueError("an answer needs text")
            g["answer"] = kw["text"].strip()
            g["groups"] = kw.get("groups") or ["all_staff"]
            g["state"] = "answered"
        elif action == "publish":
            doc_id = f"FAQ-{gap_id[2:]}"
            self.index.add({
                "id": doc_id, "title": f"FAQ: {g['question']}", "source": "lantern", "path": "Lantern / Answered questions",
                "owner": g["owner"], "groups": g["groups"], "discoverable": True, "updated": corpus.NOW,
                "review_by": "2027-05-24", "sections": [("Answer", g["answer"])],
            })
            g["doc"] = doc_id
            g["state"] = "published"
        elif action == "dismiss":
            g["reason"] = kw.get("reason", "")
            g["state"] = "dismissed"
        elif action == "reopen":
            g["state"] = "open"
        g["history"].append((g["state"], actor))
        self.log(actor, f"gap {action}", {"gap": gap_id, "state": g["state"]})
        return g

    # settings and permissions -----------------------------------------
    def set_setting(self, actor, key, value):
        if not self.is_admin(actor):
            raise Denied("only a knowledge admin can change settings")
        if key not in self.settings:
            raise KeyError(key)
        if key == "answer_threshold" and not (1.0 <= float(value) <= 12.0):
            raise ValueError("threshold must be between 1 and 12")
        old = self.settings[key]
        self.settings[key] = value
        self.log(actor, "setting", {"key": key, "old": old, "new": value})

    def permission_change(self, source, doc_id, groups):
        """A connector reports new sharing on a document. Applied before the next question."""
        doc = self.index.docs[doc_id]
        old = doc["groups"]
        doc["groups"] = list(groups)
        self.index.build()
        self.log(f"sync:{source}", "permissions", {"doc": doc_id, "old": old, "new": list(groups)})
