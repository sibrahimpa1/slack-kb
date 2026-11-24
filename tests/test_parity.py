"""The browser demo answers free-text questions with web/engine.js. It must make
the same decisions as the Python engine."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from lantern import corpus, engine
from lantern.cases import CASES

ROOT = Path(__file__).resolve().parent.parent
EXTRA = [
    "how many days off do I get", "per diem in Paris", "who do I tell about a phishing email",
    "can contractors get a home office budget", "postmortem deadline", "salary bands for sales",
    "board pack revenue", "what is the dress code", "deploy freeze over christmas", "gym allowance",
]


@pytest.mark.skipif(not shutil.which("node"), reason="node not installed")
def test_browser_engine_matches_python():
    cfg = {"stop": sorted(engine.STOP), "synonyms": engine.SYNONYMS, "defaults": engine.DEFAULTS, "now": corpus.NOW}
    qs = [(c["q"], c["who"], c["where"]) for c in CASES] + [(q, w, None) for q in EXTRA for w in corpus.USERS]
    script = """
const {make} = require(process.argv[1]);
const input = JSON.parse(require('fs').readFileSync(0, 'utf8'));
const E = make(input.cfg); const ix = new E.Index(input.docs);
const out = input.qs.map(([q, w, ch]) => { const r = E.ask(ix, q, w, ch, {}, input.users, input.channels);
  return [r.decision, r.doc, r.visibility, r.chunks, r.text || null, r.retrieved]; });
process.stdout.write(JSON.stringify(out));
"""
    inp = json.dumps({"cfg": cfg, "docs": corpus.DOCS, "users": corpus.USERS, "channels": corpus.CHANNELS, "qs": qs})
    res = subprocess.run(["node", "-e", script, str(ROOT / "web" / "engine.js")], input=inp, capture_output=True, text=True, check=True)
    js = json.loads(res.stdout)
    ix = engine.Index()
    for (q, w, ch), got in zip(qs, js):
        r = engine.ask(ix, q, w, ch)
        want = [r["decision"], r.get("doc"), r["visibility"], r["chunks"], r.get("text"), r["retrieved"]]
        assert got == want, (q, w, ch)
