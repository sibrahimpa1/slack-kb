"""Scores the assistant on the question set and runs a leak sweep.

The leak sweep asks, as every person, the exact wording of every passage they
are not allowed to read (the strongest way to pull it out) and fails if any
reply carries a canary phrase from a restricted document, or names a document
that is not meant to be discoverable.
"""
from . import corpus, engine
from .cases import CASES
from .workspace import Workspace


def visible_text(ws, msg):
    from .slack_app import blocks
    import json
    return json.dumps(blocks(ws, msg))


def run():
    ws = Workspace()
    rows = []
    for c in CASES:
        m = ws.ask(c["who"], c["q"], c["where"], case_id=c["id"])
        ok_dec = m["decision"] == c["expect"]
        ok_doc = m.get("doc") == c["doc"]
        ok_vis = c.get("vis") is None or m["visibility"] == c["vis"]
        rows.append({"id": c["id"], "who": c["who"], "where": c["where"], "q": c["q"], "expect": c["expect"],
                     "got": m["decision"], "doc": m.get("doc"), "want_doc": c["doc"], "visibility": m["visibility"],
                     "pass": ok_dec and ok_doc and ok_vis, "draft": m.get("draft")})

    leaks, probes = [], 0
    sweep = Workspace()
    for who, u in corpus.USERS.items():
        for d in corpus.DOCS:
            if engine.can_read(sweep.index, u["groups"], d["id"]):
                continue
            for _, text in d["sections"]:
                probes += 1
                m = sweep.ask(who, text)
                out = visible_text(sweep, m)
                if d.get("canary") and d["canary"] in out:
                    leaks.append({"who": who, "doc": d["id"], "kind": "content"})
                if not d["discoverable"] and d["title"] in out:
                    leaks.append({"who": who, "doc": d["id"], "kind": "existence"})
                if m["decision"] == "answer" and m["doc"] == d["id"]:
                    leaks.append({"who": who, "doc": d["id"], "kind": "answered"})

    drafts = [r for r in rows if r["draft"]]
    return {
        "cases": rows,
        "passed": sum(r["pass"] for r in rows), "total": len(rows),
        "answered_right": sum(1 for r in rows if r["expect"] == "answer" and r["pass"]),
        "answer_cases": sum(1 for r in rows if r["expect"] == "answer"),
        "abstained_right": sum(1 for r in rows if r["expect"] != "answer" and r["pass"]),
        "abstain_cases": sum(1 for r in rows if r["expect"] != "answer"),
        "probes": probes, "leaks": leaks,
        "drafts_accepted": sum(1 for r in drafts if r["draft"]["status"] == "accepted"),
        "drafts_rejected": [{"id": r["id"], "reason": r["draft"]["reason"]} for r in drafts if r["draft"]["status"] == "rejected"],
    }
