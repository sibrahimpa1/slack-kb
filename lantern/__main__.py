"""python -m lantern demo | ask "<question>" --as maya [--in eng-help] | eval | site"""
import argparse
import json
import sys

from . import corpus, evals, site
from .slack_app import blocks
from .workspace import Workspace


def show(ws, m):
    print(f"\n{corpus.USERS[m['asker']]['name']} in {('#' + m['channel']) if m['channel'] else 'a DM'}: {m['question']}")
    print(f"  -> {m['decision']} ({m['visibility']})")
    for b in blocks(ws, m):
        if b["type"] in ("section",):
            print("     " + b["text"]["text"])
        elif b["type"] == "context":
            print("     · " + b["elements"][0]["text"])
    if m.get("draft") and m["draft"]["status"] == "rejected":
        print(f"     ! model draft rejected: {m['draft']['reason']}")


def demo():
    ws = Workspace()
    picks = ["Q-02", "Q-13", "Q-17", "Q-21", "Q-25", "Q-28", "Q-30"]
    from .cases import CASES
    for c in CASES:
        if c["id"] in picks:
            show(ws, ws.ask(c["who"], c["q"], c["where"], case_id=c["id"]))
    g = ws.gaps[0]
    print(f"\nKnowledge gap {g['id']}: \"{g['question']}\" routed to {corpus.USERS[g['owner']]['name']}")
    ws.move(g["id"], "ruth", "assign", to="ruth")
    ws.move(g["id"], "ruth", "answer", text="Dogs are welcome in the Berlin office on Fridays if they are house-trained and stay off the kitchen floor.")
    ws.move(g["id"], "ruth", "publish")
    show(ws, ws.ask("maya", "Can I bring my dog to the office?"))
    r = evals.run()
    print(f"\nEvals: {r['passed']}/{r['total']} questions behave as expected; leak sweep: {r['probes']} probes, {len(r['leaks'])} leaks;"
          f" model drafts rejected by code: {len(r['drafts_rejected'])}.")
    return 0 if r["passed"] == r["total"] and not r["leaks"] else 1


def main(argv=None):
    p = argparse.ArgumentParser(prog="lantern")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("demo")
    a = sub.add_parser("ask")
    a.add_argument("question")
    a.add_argument("--as", dest="who", default="maya", choices=sorted(corpus.USERS))
    a.add_argument("--in", dest="channel", choices=sorted(corpus.CHANNELS))
    sub.add_parser("eval")
    s = sub.add_parser("site")
    s.add_argument("--out", default="site/index.html")
    args = p.parse_args(argv)
    if args.cmd == "demo":
        return demo()
    if args.cmd == "ask":
        ws = Workspace()
        show(ws, ws.ask(args.who, args.question, args.channel))
        return 0
    if args.cmd == "eval":
        r = evals.run()
        print(json.dumps({k: v for k, v in r.items() if k != "cases"}, indent=2))
        return 0 if r["passed"] == r["total"] and not r["leaks"] else 1
    if args.cmd == "site":
        site.build(args.out)
        print(f"wrote {args.out}")
        return 0


if __name__ == "__main__":
    sys.exit(main())
