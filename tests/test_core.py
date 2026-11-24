import json

import pytest

from lantern import answer, connectors, corpus, engine, evals, slack_app
from lantern.cases import CASES
from lantern.workspace import Denied, Workspace


@pytest.fixture
def ws():
    return Workspace()


@pytest.mark.parametrize("case", CASES, ids=[c["id"] for c in CASES])
def test_every_case_behaves(ws, case):
    m = ws.ask(case["who"], case["q"], case["where"], case_id=case["id"])
    assert m["decision"] == case["expect"]
    assert m.get("doc") == case["doc"]
    if case.get("vis"):
        assert m["visibility"] == case["vis"]


def test_leak_sweep_finds_nothing():
    r = evals.run()
    assert r["leaks"] == []
    assert r["probes"] > 50
    assert r["passed"] == r["total"]


def test_current_policy_beats_the_archived_one(ws):
    m = ws.ask("jonas", "What is the daily allowance for meals on business travel?")
    assert m["doc"] == "D-01"
    assert "55" in m["text"] and "45" not in m["text"]
    assert m["superseded_seen"] == ["D-02"]


def test_restricted_doc_named_only_when_discoverable(ws):
    hint = ws.ask("maya", "What is the salary band for an engineer L3?")
    assert hint["decision"] == "restricted" and hint["doc"] == "D-05"
    hidden = ws.ask("maya", "Are the Platform and Data teams going to merge?")
    assert hidden["decision"] == "unknown"
    assert "Q1 organisation" not in json.dumps(slack_app.blocks(ws, hidden))


def test_hint_can_be_switched_off(ws):
    ws.set_setting("ruth", "hint_restricted", False)
    m = ws.ask("maya", "What is the salary band for an engineer L3?")
    assert m["decision"] == "unknown"


def test_channel_answer_only_uses_what_every_member_can_read(ws):
    m = ws.ask("ana", "Who approves a discount above 20% or a multi-year price lock?", "ask-people-ops")
    assert m["visibility"] == "ephemeral"
    out = slack_app.reply(ws, m, "C01PEOPLE")
    assert out["method"] == "chat.postEphemeral" and out["user"] == corpus.USERS["ana"]["slack"]


def test_not_a_member_cannot_ask_in_channel(ws):
    with pytest.raises(Denied):
        ws.ask("dev", "deploy windows", "sales-floor")


def test_stale_page_is_flagged_and_reviewed(ws):
    m = ws.ask("maya", "How much can I spend on courses and conferences each year?")
    assert m["stale"] is True  # benefits page is past its review date
    assert any(r["doc"] == "D-14" for r in ws.reviews)


# model drafts ---------------------------------------------------------------

def test_draft_with_invented_number_is_rejected(ws):
    m = ws.ask("jonas", "Who has to approve an expense over 500 euros?", case_id="Q-09")
    assert m["draft"]["status"] == "rejected" and "300" in m["draft"]["reason"]
    assert "300" not in m["text"] and "500" in m["text"]


def test_draft_citing_unseen_passage_is_rejected(ws):
    m = ws.ask("dev", "How fast do I need to acknowledge a Sev1 page when on call?", "eng-help", case_id="Q-12")
    assert m["draft"]["status"] == "rejected" and "D-09#2" in m["draft"]["reason"]
    assert "break-glass" not in m["text"]


def test_draft_citing_archive_is_rejected(ws):
    m = ws.ask("jonas", "What is the daily allowance for meals on business travel?", case_id="Q-30")
    assert m["draft"]["status"] == "rejected"
    assert "EUR 55" in m["text"]


def test_good_draft_is_used_without_citation_markers(ws):
    m = ws.ask("jonas", "Who approves a 15% discount on a deal?", "sales-floor", case_id="Q-14")
    assert m["draft"]["status"] == "accepted"
    assert "sales manager" in m["text"] and "[" not in m["text"]


def test_numbers_in_question_may_be_repeated():
    ix = engine.Index()
    draft = {"answer": "15% needs the sales manager.", "citations": ["D-10#1"]}
    assert answer.validate(draft, ["D-10#1"], ix, "who approves 15%?") is None
    assert answer.validate(draft, ["D-10#1"], ix, "who approves this?") is not None


def test_draft_without_citations_is_rejected():
    assert answer.validate({"answer": "Yes.", "citations": []}, ["D-01#1"], engine.Index()) == "no citations"


# knowledge gaps --------------------------------------------------------------

def test_gap_flow_publishes_an_answer_the_next_person_gets(ws):
    first = ws.ask("jonas", "Can I bring my dog to the office?", "ask-people-ops")
    assert first["decision"] == "unknown"
    g = ws.gaps[-1]
    assert g["owner"] == "ruth" and g["state"] == "open"
    ws.move(g["id"], "ruth", "assign", to="ruth")
    ws.move(g["id"], "ruth", "answer", text="Dogs are welcome in the office on Fridays if they are house-trained.")
    ws.move(g["id"], "ruth", "publish")
    again = ws.ask("maya", "Can I bring my dog to the office?")
    assert again["decision"] == "answer" and again["doc"].startswith("FAQ-")


def test_gap_roles_and_order(ws):
    ws.ask("maya", "Is there a company car scheme?")
    gid = ws.gaps[-1]["id"]
    with pytest.raises(Denied):
        ws.move(gid, "maya", "assign", to="maya")      # not an admin
    with pytest.raises(Denied):
        ws.move(gid, "ruth", "publish")                 # nothing answered yet
    ws.move(gid, "ruth", "assign", to="ana")
    with pytest.raises(Denied):
        ws.move(gid, "jonas", "answer", text="x")       # not the owner
    with pytest.raises(ValueError):
        ws.move(gid, "ana", "answer", text="  ")
    ws.move(gid, "ana", "answer", text="There is no company car scheme.", groups=["all_staff"])
    ws.move(gid, "ana", "publish")
    assert ws.gap(gid)["state"] == "published"


def test_faq_respects_the_groups_it_was_published_for(ws):
    ws.ask("maya", "Is there a company car scheme?")
    gid = ws.gaps[-1]["id"]
    ws.move(gid, "ruth", "assign", to="ana")
    ws.move(gid, "ana", "answer", text="Company cars are only for the leadership team.", groups=["leadership"])
    ws.move(gid, "ana", "publish")
    assert ws.ask("leo", "Is there a company car scheme?")["decision"] == "answer"
    assert ws.ask("maya", "Is there a company car scheme?")["decision"] != "answer"


def test_feedback_routes_to_owner(ws):
    m = ws.ask("maya", "Can I carry over unused vacation days?")
    ws.feedback(m["id"], "maya", "outdated")
    ws.feedback(m["id"], "maya", "not_helpful")
    assert ws.reviews[-1]["doc"] == "D-04" and ws.reviews[-1]["owner"] == "ruth"
    assert ws.gaps[-1]["kind"] == "answer not helpful"


# settings, permissions, audit ----------------------------------------------

def test_only_admins_change_settings(ws):
    with pytest.raises(Denied):
        ws.set_setting("maya", "answer_threshold", 2)
    with pytest.raises(ValueError):
        ws.set_setting("ruth", "answer_threshold", 40)
    ws.set_setting("ruth", "answer_threshold", 6)
    assert ws.audit[-1]["action"] == "setting"


def test_revoked_access_applies_to_the_next_question(ws):
    assert ws.ask("jonas", "When is pay day in December?")["decision"] == "answer"
    ws.permission_change("drive", "D-18", ["finance"])
    assert ws.ask("jonas", "When is pay day in December?")["decision"] != "answer"


def test_audit_keeps_or_drops_question_text(ws):
    ws.ask("maya", "When is pay day in December?")
    assert ws.audit[-1]["question"].startswith("When")
    ws.set_setting("leo", "log_question_text", False)
    ws.ask("maya", "When is pay day in December?")
    assert ws.audit[-1]["question"] == "(not stored)"
    assert ws.audit[-1]["docs"] == ["D-18"]


def test_connectors_fail_closed_on_unknown_principals():
    drive = connectors.sync("drive")
    w = {x["doc"]: x for x in drive["warnings"]}
    assert "D-15" in w
    d15 = next(d for d in drive["docs"] if d["doc"] == "D-15")
    assert d15["groups"] == ["leadership"]
    for s in connectors.sync_all():
        for d in s["docs"]:
            assert sorted(d["groups"]) == sorted(corpus.DOC_BY_ID[d["doc"]]["groups"])


# Slack layer ----------------------------------------------------------------

SECRET = "test-signing-secret"


def signed(body, ts=1_800_000_000, ctype="application/json"):
    return {"X-Slack-Request-Timestamp": str(ts), "X-Slack-Signature": slack_app.sign(SECRET, ts, body),
            "Content-Type": ctype}


def test_signature_checks():
    body = '{"type":"url_verification","challenge":"abc"}'
    h = slack_app.Handler(Workspace(), SECRET)
    assert h.handle(signed(body), body, now=1_800_000_010) == (200, {"challenge": "abc"})
    assert h.handle(signed(body), body, now=1_800_000_400)[0] == 401          # too old: replay
    bad = {**signed(body), "X-Slack-Signature": "v0=00"}
    assert h.handle(bad, body, now=1_800_000_010)[0] == 401


def test_mention_in_channel_replies_in_thread_and_dedupes():
    h = slack_app.Handler(Workspace(), SECRET)
    ev = {"type": "event_callback", "event_id": "Ev1", "event": {
        "type": "app_mention", "user": "U02JONAS", "channel": "C01PEOPLE", "ts": "171.1",
        "text": "<@ULANTERN> How many weeks of parental leave does the primary caregiver get?"}}
    body = json.dumps(ev)
    code, out = h.handle(signed(body), body, now=1_800_000_001)
    assert code == 200 and out["method"] == "chat.postMessage" and out["thread_ts"] == "171.1"
    assert "20 weeks" in json.dumps(out["blocks"])
    assert h.handle(signed(body), body, now=1_800_000_002)[1] == {"duplicate": True}


def test_dm_and_unknown_users_and_bots():
    h = slack_app.Handler(Workspace(), SECRET)
    for i, (user, extra, expect) in enumerate([("U01MAYA", {}, "chat.postMessage"), ("U99X", {}, None), ("U01MAYA", {"bot_id": "B1"}, None)]):
        ev = {"type": "event_callback", "event_id": f"E{i}", "event": {"type": "message", "channel_type": "im",
              "user": user, "channel": "D1", "text": "When is pay day in December?", **extra}}
        body = json.dumps(ev)
        out = h.handle(signed(body), body, now=1_800_000_001)[1]
        assert out.get("method") == expect


def test_slash_command_is_private_and_buttons_give_feedback():
    ws = Workspace()
    h = slack_app.Handler(ws, SECRET)
    form = "user_id=U01MAYA&command=%2Fask&text=When+is+pay+day+in+December%3F"
    code, out = h.handle(signed(form, ctype="application/x-www-form-urlencoded"), form, now=1_800_000_001)
    assert out["response_type"] == "ephemeral"
    msg_id = ws.messages[-1]["id"]
    payload = json.dumps({"user": {"id": "U01MAYA"}, "actions": [{"action_id": "outdated", "value": msg_id}]})
    from urllib.parse import quote
    form2 = "payload=" + quote(payload)
    code, out = h.handle(signed(form2, ctype="application/x-www-form-urlencoded"), form2, now=1_800_000_001)
    assert "review task" in out["text"] and ws.reviews[-1]["doc"] == "D-18"
    empty = "user_id=U01MAYA&command=%2Fask&text="
    assert "Ask me anything" in h.handle(signed(empty, ctype="application/x-www-form-urlencoded"), empty, now=1_800_000_001)[1]["text"]
