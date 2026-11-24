"""Builds the self-contained live demo (site/index.html) from the Python
engine's own data and results, with the browser port of the engine inlined."""
import json
from pathlib import Path

from . import connectors, corpus, engine, evals
from .cases import CASES
from .workspace import Workspace

WEB = Path(__file__).resolve().parent.parent / "web"


def payload():
    ws = Workspace()
    msgs = []
    for c in CASES:
        m = ws.ask(c["who"], c["q"], c["where"], case_id=c["id"])
        m["case"] = c["id"]
        msgs.append(m)
    # a little history on the knowledge desk so the queue is not empty
    ws.feedback(msgs[6]["id"], "ruth", "helpful")
    ws.feedback(msgs[10]["id"], "maya", "outdated")
    by_q = {g["question"]: g["id"] for g in ws.gaps}
    g = by_q["What was Q3 revenue against plan and what is the runway?"]
    ws.move(g, "leo", "dismiss", reason="Board figures are shared at the all-hands, not through Lantern")
    g = by_q["Is there a company car scheme?"]
    ws.move(g, "ruth", "assign", to="ana")
    ws.move(g, "ana", "answer", text="There is no company car scheme. Use the travel desk for rental cars on business trips.", groups=["all_staff"])
    g = by_q["What is the wifi password for guests?"]
    ws.move(g, "ruth", "assign", to="ruth")
    ws.move(g, "ruth", "answer", text="The guest wifi password is shown on the reception screen and changes every Monday.", groups=["all_staff", "contractors"])
    ws.move(g, "ruth", "publish")
    ev = evals.run()
    return {
        "now": corpus.NOW, "company": corpus.COMPANY, "groups": corpus.GROUPS, "users": corpus.USERS,
        "admins": corpus.ADMINS, "channels": corpus.CHANNELS, "sources": corpus.SOURCES,
        "docs": list(ws.index.docs.values()), "cases": CASES, "messages": msgs, "gaps": ws.gaps, "reviews": ws.reviews,
        "audit": ws.audit, "sync": connectors.sync_all(),
        "evals": {k: v for k, v in ev.items()},
        "engine": {"stop": sorted(engine.STOP), "synonyms": engine.SYNONYMS,
                   "defaults": engine.DEFAULTS, "now": corpus.NOW},
    }


def build(out="site/index.html"):
    html = (WEB / "index.html").read_text()
    data = json.dumps(payload(), separators=(",", ":")).replace("</", "<\\/")
    html = (html.replace("/*CSS*/", (WEB / "style.css").read_text())
                .replace("/*DATA*/", "window.LANTERN = " + data + ";")
                .replace("/*ENGINE*/", (WEB / "engine.js").read_text())
                .replace("/*APP*/", (WEB / "app.js").read_text()))
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text(html)
    return out
