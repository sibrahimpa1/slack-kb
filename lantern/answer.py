"""The model phrases the answer; code checks it before anyone sees it.

A draft is accepted only if every citation points at a passage the reader was
allowed to see and that retrieval actually returned, no archived version is
cited, and every number in the text appears in the cited passages. Otherwise
the reader gets the plain extract from the document, and the rejection is logged.

Offline (the default) the drafts come from recorded.json, so the demo and CI
need no API key. LANTERN_LIVE=1 with ANTHROPIC_API_KEY calls Claude instead.
"""
import json
import os
import re
from pathlib import Path

RECORDED = json.loads((Path(__file__).parent / "recorded.json").read_text())

MODEL = "claude-opus-5-5"

SCHEMA = {
    "type": "object",
    "properties": {
        "answer": {"type": "string"},
        "citations": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["answer", "citations"],
    "additionalProperties": False,
}

PROMPT = """You answer an employee's question from the company passages below.
Use only these passages. Cite every passage you rely on by its id, like [D-01#2].
Keep it to two or three sentences, in plain words. If the passages do not answer
the question, say so and cite nothing.

Question: {question}

Passages:
{passages}"""

NUM = re.compile(r"\d[\d,.]*\d|\d")


def numbers(text):
    return {n.replace(",", "").rstrip(".") for n in NUM.findall(text)}


CITE = re.compile(r"\[[A-Z]+-\d+#\d+\]")


def validate(draft, allowed_chunks, index, question=""):
    """Return None if the draft is usable, else the reason it was rejected."""
    cites = draft.get("citations") or []
    if not cites:
        return "no citations"
    by_id = {c["id"]: c for c in index.chunks}
    for c in cites:
        if c not in allowed_chunks:
            return f"cites {c}, which was not among the passages this reader may see"
        if index.docs[by_id[c]["doc"]].get("superseded_by"):
            return f"cites {c} from an archived version"
    source_numbers = set()
    for c in cites:
        source_numbers |= numbers(by_id[c]["text"])
    source_numbers |= numbers(question)  # "who approves 15%?" may repeat the 15
    stray = sorted(numbers(CITE.sub("", draft["answer"])) - source_numbers)
    if stray:
        return f"states {', '.join(stray)}, which is not in the cited passages"
    return None


def live_draft(question, passages):
    import anthropic  # only needed in live mode

    client = anthropic.Anthropic()
    text = "\n".join(f"[{c['id']}] {c['heading']}: {c['text']}" for c in passages)
    msg = client.beta.messages.create(
        model=MODEL,
        max_tokens=600,
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        output_config={"effort": "low", "format": {"type": "json_schema", "schema": SCHEMA}},
        messages=[{"role": "user", "content": PROMPT.format(question=question, passages=text)}],
    )
    if msg.stop_reason == "refusal":
        return None
    return json.loads("".join(b.text for b in msg.content if b.type == "text"))


def draft_for(case_id, question, passages):
    if os.environ.get("LANTERN_LIVE") == "1":
        return live_draft(question, passages)
    return RECORDED.get(case_id)


def compose(index, result, question, case_id=None):
    """Turn an engine decision into the message text plus a record of what happened."""
    if result["decision"] != "answer":
        return {**result, "draft": None}
    allowed = result["retrieved"]
    by_id = {c["id"]: c for c in index.chunks}
    passages = [by_id[c] for c in allowed]
    draft = draft_for(case_id, question, passages) if case_id or os.environ.get("LANTERN_LIVE") == "1" else None
    if draft is None:
        return {**result, "draft": None}
    reason = validate(draft, allowed, index, question)
    if reason:
        return {**result, "draft": {"status": "rejected", "reason": reason, "text": draft["answer"]}}
    clean = re.sub(r"\s+", " ", CITE.sub("", draft["answer"])).strip()
    return {**result, "text": clean, "chunks": draft["citations"],
            "draft": {"status": "accepted"}}
