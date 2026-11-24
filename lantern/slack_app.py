"""Slack side: request signing, event routing, Block Kit messages.

handle() takes the raw request Slack would send to the Events API, the /ask
slash command or an interactive button, and returns what to send back. It is
plain Python so it is fully tested; bolt_app() wires the same handlers into a
Slack Bolt app when you deploy with real tokens (SLACK_BOT_TOKEN,
SLACK_SIGNING_SECRET).
"""
import hashlib
import hmac
import json
import time
from urllib.parse import parse_qs

from . import corpus

MAX_AGE = 300  # seconds; Slack's guidance against replayed requests


def sign(secret, ts, body):
    base = f"v0:{ts}:{body}".encode()
    return "v0=" + hmac.new(secret.encode(), base, hashlib.sha256).hexdigest()


def verify(secret, ts, body, signature, now=None):
    now = time.time() if now is None else now
    try:
        if abs(now - int(ts)) > MAX_AGE:
            return False
    except (TypeError, ValueError):
        return False
    return hmac.compare_digest(sign(secret, ts, body), signature or "")


SLACK_TO_USER = {u["slack"]: k for k, u in corpus.USERS.items()}
CHANNEL_IDS = {"C01PEOPLE": "ask-people-ops", "C02ENG": "eng-help", "C03SALES": "sales-floor"}


def source_line(ws, chunks):
    out = []
    for c in chunks:
        doc = ws.index.docs[c.split("#")[0]]
        out.append(f"{doc['title']} ({corpus.SOURCES.get(doc['source'], {'name': 'Lantern'})['name']}, updated {doc['updated']})")
    return " · ".join(out)


def blocks(ws, msg):
    """The Block Kit payload for one assistant reply."""
    who = corpus.USERS
    if msg["decision"] == "answer":
        text = msg["text"]
        b = [{"type": "section", "text": {"type": "mrkdwn", "text": text}},
             {"type": "context", "elements": [{"type": "mrkdwn", "text": "Sources: " + source_line(ws, msg["chunks"])}]}]
        if msg.get("stale"):
            b.append({"type": "context", "elements": [{"type": "mrkdwn", "text": f"This page is past its review date. I've let {who[msg['owner']]['name']} know."}]})
        if msg.get("superseded_seen"):
            b.append({"type": "context", "elements": [{"type": "mrkdwn", "text": "An older version of this policy exists; I used the current one."}]})
        if msg.get("visibility") == "ephemeral":
            b.append({"type": "context", "elements": [{"type": "mrkdwn", "text": "Only you can see this: it uses a document not everyone here can read."}]})
        b.append({"type": "actions", "elements": [
            {"type": "button", "text": {"type": "plain_text", "text": "Helpful"}, "action_id": "helpful", "value": msg["id"]},
            {"type": "button", "text": {"type": "plain_text", "text": "Not helpful"}, "action_id": "not_helpful", "value": msg["id"]},
            {"type": "button", "text": {"type": "plain_text", "text": "Flag as outdated"}, "action_id": "outdated", "value": msg["id"]},
        ]})
        return b
    if msg["decision"] == "restricted":
        doc = ws.index.docs[msg["doc"]]
        return [{"type": "section", "text": {"type": "mrkdwn", "text": (
            f"There is a document on this, *{doc['title']}*, but it isn't shared with you, so I can't use it. "
            f"{who[msg['owner']]['name']} owns it and can tell you what you're able to know.")}}]
    return [{"type": "section", "text": {"type": "mrkdwn", "text": (
        f"I couldn't find this written down anywhere I can read. I've asked {who[msg['owner']]['name']}, "
        "and the answer will be added so the next person gets it straight away.")}}]


def reply(ws, msg, channel_id):
    payload = {"channel": channel_id, "blocks": blocks(ws, msg), "text": msg.get("text") or "Lantern reply"}
    if msg["visibility"] == "ephemeral":
        return {"method": "chat.postEphemeral", "user": corpus.USERS[msg["asker"]]["slack"], **payload}
    return {"method": "chat.postMessage", **payload}


class Handler:
    def __init__(self, ws, secret):
        self.ws = ws
        self.secret = secret
        self.seen = set()

    def handle(self, headers, body, now=None):
        if not verify(self.secret, headers.get("X-Slack-Request-Timestamp"), body,
                      headers.get("X-Slack-Signature"), now):
            return 401, {"error": "bad signature"}
        if headers.get("Content-Type", "").startswith("application/x-www-form-urlencoded"):
            form = {k: v[0] for k, v in parse_qs(body).items()}
            if "payload" in form:
                return self.action(json.loads(form["payload"]))
            return self.command(form)
        data = json.loads(body)
        if data.get("type") == "url_verification":
            return 200, {"challenge": data["challenge"]}
        if data.get("type") != "event_callback":
            return 200, {}
        if data["event_id"] in self.seen:  # Slack retries; answer once
            return 200, {"duplicate": True}
        self.seen.add(data["event_id"])
        ev = data["event"]
        if ev.get("bot_id"):
            return 200, {}
        user = SLACK_TO_USER.get(ev.get("user"))
        if not user:
            return 200, {"ignored": "unknown user"}
        text = " ".join(w for w in ev.get("text", "").split() if not w.startswith("<@"))
        if ev["type"] == "app_mention":
            channel = CHANNEL_IDS.get(ev["channel"])
            msg = self.ws.ask(user, text, channel)
            out = reply(self.ws, msg, ev["channel"])
            out["thread_ts"] = ev.get("ts")
            return 200, out
        if ev["type"] == "message" and ev.get("channel_type") == "im":
            msg = self.ws.ask(user, text)
            return 200, reply(self.ws, msg, ev["channel"])
        return 200, {}

    def command(self, form):
        user = SLACK_TO_USER.get(form.get("user_id"))
        if not user:
            return 200, {"response_type": "ephemeral", "text": "I don't know who you are yet."}
        if not form.get("text", "").strip():
            return 200, {"response_type": "ephemeral", "text": "Ask me anything, for example: /ask how many days of leave do I get?"}
        msg = self.ws.ask(user, form["text"])  # slash commands answer privately
        return 200, {"response_type": "ephemeral", "blocks": blocks(self.ws, msg)}

    def action(self, payload):
        user = SLACK_TO_USER.get(payload["user"]["id"])
        act = payload["actions"][0]
        self.ws.feedback(act["value"], user, act["action_id"])
        thanks = {"helpful": "Thanks, noted.", "not_helpful": "Thanks. I've sent this to the page owner to improve.",
                  "outdated": "Thanks. The page owner has a review task now."}[act["action_id"]]
        return 200, {"response_type": "ephemeral", "replace_original": False, "text": thanks}


def bolt_app(ws):  # pragma: no cover - needs real Slack credentials
    import os

    from slack_bolt import App

    app = App(token=os.environ["SLACK_BOT_TOKEN"], signing_secret=os.environ["SLACK_SIGNING_SECRET"])
    h = Handler(ws, os.environ["SLACK_SIGNING_SECRET"])

    @app.event("app_mention")
    def mention(event, client):
        user = SLACK_TO_USER.get(event["user"])
        msg = ws.ask(user, event["text"], CHANNEL_IDS.get(event["channel"]))
        out = reply(ws, msg, event["channel"])
        method = out.pop("method")
        getattr(client, method.replace(".", "_"))(thread_ts=event.get("ts"), **out)

    @app.command("/ask")
    def ask(ack, command, respond):
        ack()
        respond(h.command(command)[1])

    for action_id in ("helpful", "not_helpful", "outdated"):
        @app.action(action_id)
        def act(ack, body, respond):
            ack()
            respond(h.action(body)[1])

    return app
