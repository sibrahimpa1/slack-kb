"""Retrieval and the answer decision. Code decides who may see what and
whether there is enough evidence to answer; the model only phrases answers.

The browser demo carries a port of this file (site/engine.js). tests/test_parity.py
runs both on the same questions and requires identical decisions.
"""
import math
import re

from . import corpus

STOP = set("""a an and are as at be by can do does for from get got have how i if in is it its me my of on or our
should so that the their them there this to us we what when where which who why will with you your
much many any about after before am was were has had did not no yes than then just also into out up""".split())

# Words people type versus words the documents use.
SYNONYMS = {
    "maternity": "parental", "paternity": "parental", "vacation": "leave", "holiday": "leave",
    "holidays": "leave", "pto": "leave", "wfh": "home", "salaries": "salary", "paycheck": "pay",
    "payday": "pay", "laptop": "laptops", "gym": "wellbeing", "deploying": "deploy", "release": "deploy",
    "prod": "production", "discounts": "discount", "hotel": "hotels", "allowance": "allowance",
    "expense": "expenses", "reimburse": "reimbursed", "oncall": "call",
    "off": "leave", "phishing": "suspicious", "clicked": "click", "hacked": "suspicious",
    "approve": "approval", "approves": "approval", "approved": "approval", "approvals": "approval",
}

DEFAULTS = {
    "answer_threshold": 4.0,    # minimum BM25 score of the best visible passage
    "min_terms": 2,             # distinct query words the passage must contain
    "hint_restricted": True,    # say that a discoverable document exists but is not yours to read
    "superseded_weight": 0.4,   # archived versions rank lower and are never the only source
    "top_k": 4,
}

K1, B = 1.5, 0.75


def stem(t):
    if len(t) > 4 and t.endswith("ies"):
        return t[:-3] + "y"
    if len(t) > 3 and t.endswith("s") and not t.endswith("ss"):
        return t[:-1]
    return t


def tokenize(text):
    out = []
    for t in re.sub(r"[^a-z0-9]+", " ", text.lower()).split():
        t = SYNONYMS.get(t, t)
        if t in STOP or (len(t) < 2 and not t.isdigit()):
            continue
        out.append(stem(t))
    return out


class Index:
    def __init__(self, docs=None):
        self.docs = {d["id"]: d for d in (docs if docs is not None else corpus.DOCS)}
        self.build()

    def add(self, doc):
        self.docs[doc["id"]] = doc
        self.build()

    def build(self):
        self.chunks = corpus.chunks(list(self.docs.values()))
        self.tf = []
        df = {}
        for c in self.chunks:
            toks = tokenize(c["search"])
            counts = {}
            for t in toks:
                counts[t] = counts.get(t, 0) + 1
            self.tf.append((counts, len(toks)))
            for t in counts:
                df[t] = df.get(t, 0) + 1
        n = len(self.chunks)
        self.avgdl = sum(l for _, l in self.tf) / n
        self.idf = {t: math.log(1 + (n - f + 0.5) / (f + 0.5)) for t, f in df.items()}

    def score(self, q_terms, i):
        counts, dl = self.tf[i]
        s = 0.0
        for t in q_terms:
            f = counts.get(t, 0)
            if f:
                s += self.idf[t] * f * (K1 + 1) / (f + K1 * (1 - B + B * dl / self.avgdl))
        return s

    def search(self, question, doc_ok, settings):
        q_terms = sorted(set(tokenize(question)))
        hits = []
        for i, c in enumerate(self.chunks):
            if not doc_ok(c["doc"]):
                continue
            s = self.score(q_terms, i)
            if s <= 0:
                continue
            if self.docs[c["doc"]].get("superseded_by"):
                s *= settings["superseded_weight"]
            matched = sum(1 for t in q_terms if t in self.tf[i][0])
            hits.append({"chunk": c["id"], "doc": c["doc"], "score": round(s, 6), "matched": matched})
        hits.sort(key=lambda h: (-h["score"], h["chunk"]))
        return q_terms, hits


def can_read(index, groups, doc_id):
    return bool(set(groups) & set(index.docs[doc_id]["groups"]))


def visible_to_all(index, members, doc_id, users=None):
    users = users or corpus.USERS
    return all(can_read(index, users[m]["groups"], doc_id) for m in members)


def strong(hit, settings):
    return hit["score"] >= settings["answer_threshold"] and hit["matched"] >= settings["min_terms"]


def sentences(text):
    return [s.strip() for s in re.split(r"(?<=\.)\s+", text) if s.strip()]


def extract(chunk, q_terms):
    """Pick the one or two sentences that carry the answer, in reading order."""
    sents = sentences(chunk["text"])
    scored = []
    for i, s in enumerate(sents):
        st = set(tokenize(s))
        scored.append((-sum(1 for t in q_terms if t in st), i))
    scored.sort()
    keep = [scored[0][1]] if scored[0][0] < 0 else [0]
    if len(scored) > 1 and scored[1][0] <= -2:
        keep.append(scored[1][1])
    keep.sort()
    return " ".join(sents[i] for i in keep)


def decide(index, question, can_see, settings=None):
    """can_see(doc_id) -> bool for the people who will read the answer."""
    settings = {**DEFAULTS, **(settings or {})}
    q_terms, hits = index.search(question, can_see, settings)
    chunk_by_id = {c["id"]: c for c in index.chunks}
    top = [h for h in hits if not index.docs[h["doc"]].get("superseded_by")]
    best = top[0] if top else None
    # Only current documents can carry an answer; archived ones may be shown as context.
    if best and strong(best, settings):
        chunk = chunk_by_id[best["chunk"]]
        doc = index.docs[best["doc"]]
        cites = [best["chunk"]]
        for h in top[1:settings["top_k"]]:
            if h["doc"] != best["doc"] and strong(h, settings) and h["score"] >= best["score"] * 0.8:
                cites.append(h["chunk"])
                break
        older = [h["doc"] for h in hits if index.docs[h["doc"]].get("superseded_by") == best["doc"]]
        return {
            "decision": "answer", "doc": best["doc"], "chunks": cites, "terms": q_terms,
            "text": extract(chunk, q_terms), "stale": doc["review_by"] < corpus.NOW,
            "superseded_seen": sorted(set(older)), "owner": doc["owner"],
            "retrieved": [h["chunk"] for h in hits[: settings["top_k"]]],
        }
    # Not answerable from what these readers can see. Is there something they cannot see?
    _, hidden = index.search(question, lambda d: not can_see(d), settings)
    hidden = [h for h in hidden if strong(h, settings) and not index.docs[h["doc"]].get("superseded_by")]
    route = best["doc"] if best else None
    if hidden and settings["hint_restricted"] and index.docs[hidden[0]["doc"]]["discoverable"]:
        d = index.docs[hidden[0]["doc"]]
        return {"decision": "restricted", "doc": d["id"], "owner": d["owner"], "terms": q_terms,
                "chunks": [], "retrieved": []}
    owner = index.docs[route]["owner"] if route else "ruth"
    return {"decision": "unknown", "doc": None, "owner": owner, "near": route, "terms": q_terms,
            "chunks": [], "retrieved": [h["chunk"] for h in hits[: settings["top_k"]]]}


def ask(index, question, asker, channel=None, settings=None, users=None, channels=None):
    """Answer for a person in a DM or a channel.

    In a channel the answer may only use documents every member can read. If the
    asker could see more, the fuller answer goes to them privately (ephemeral).
    """
    users = users or corpus.USERS
    channels = channels or corpus.CHANNELS
    mine = users[asker]["groups"]
    personal = decide(index, question, lambda d: can_read(index, mine, d), settings)
    if personal["decision"] == "unknown" and personal["owner"] == asker:
        personal["owner"] = "leo" if asker == "ruth" else "ruth"  # never route a gap back to the person asking
    if channel is None:
        return {**personal, "visibility": "dm"}
    members = channels[channel]["members"]
    public = decide(index, question, lambda d: visible_to_all(index, members, d, users), settings)
    if public["decision"] == "answer":
        return {**public, "visibility": "channel"}
    if personal["decision"] == "answer":
        return {**personal, "visibility": "ephemeral", "why_private": "uses a document not everyone in this channel can read"}
    if personal["decision"] == "restricted":
        return {**personal, "visibility": "ephemeral"}
    return {**personal, "visibility": "channel"}
