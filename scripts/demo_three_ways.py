"""One question, three ways — from stored real-data runs, no model calls.

  python demo_three_ways.py --list            rank demo candidates (stale answer wrong; compressed answer wrong and
                                              unanimously certified by three judges; resolved value right)
  python demo_three_ways.py --qid R3-...      print the three-way story for one question
"""
import argparse
import json
import re
import os
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
# Inputs and outputs live in one working folder (default ../work, built by prepare_work.py); override with WVV_WORK.
HERE = Path(os.environ.get("WVV_WORK", str(SCRIPTS.parent / "work")))
cases = {c["qid"]: c for c in json.loads((HERE / "fr-cases-100-v3.json").read_text(encoding="utf-8"))}
run = {r["qid"]: r for r in json.loads((HERE / "fr-gpt54-100v3-20260921.json").read_text(encoding="utf-8"))["rows"]}
resolved = {r["qid"]: r for r in json.loads((HERE / "fr-events-v4-gpt54-100v3-20260921.rescored.json").read_text(encoding="utf-8"))["rows"]}
events = {r["qid"]: r["events"] for r in json.loads((HERE / "fr-events-v4-gpt54-100v3-20260921.json").read_text(encoding="utf-8"))["rows"]}
judges = {j: {r["qid"]: r["conds"] for r in json.loads((HERE / f"fr-judge-{j}-g100v3-20260921.json").read_text(encoding="utf-8"))} for j in ("mini", "gpt54", "deepseek")}
HDR = re.compile(r"\[Article (.+?) — version en vigueur du (\S+) au (.+?)\]")


def panel(qid, cond):
    return {j: judges[j][qid].get(cond) for j in judges}


def score(qid):
    r = run[qid]; s = 0
    s += 3 * (not r["conds"]["B_current"]["correct"])
    s += 3 * (not r["conds"]["A_compressed"]["correct"] and all(v == "supported" for v in panel(qid, "A_compressed").values()))
    s += 2 * resolved[qid]["correct"]
    s += 1 * r["conds"]["C_gold"]["correct"]
    return s


def show(qid):
    c, r, rv = cases[qid], run[qid], resolved[qid]
    print(f"\n=== {qid}\nQUESTION (as of {c['date_anchor']}): {c['prompt']}\nBENCHMARK GOLD: {c['canonical_answer']}\n")
    b = r["conds"]["B_current"]; a = r["conds"]["A_compressed"]; g = r["conds"]["C_gold"]
    print(f"1) STATIC RAG — today's version of the article ({HDR.search(c['current_text']).group(2)} → {HDR.search(c['current_text']).group(3)}):")
    print(f"   answer: {b['answer']}\n   correct: {b['correct']} | own verifier: {b['verifier']} | panel: {panel(qid, 'B_current')}")
    print(f"\n2) MULTI-STAGE — compressed history ({r['compressed_chars']} chars from {len(c['history_text'])}):")
    print(f"   answer: {a['answer']}\n   correct: {a['correct']} | own verifier: {a['verifier']} | panel: {panel(qid, 'A_compressed')}")
    print(f"\n3) JOURNAL — one typed figure per version, time owned by the data model, resolve on {c['date_anchor']}:")
    for e in events[qid]:
        print(f"   {e['kind']:7s} {e['value']:>14s}  valid {e['effective_at']} → {e['expires'] or 'open'}")
    print(f"   resolved: {rv['value']}  status {rv['status']}  correct: {rv['correct']}")
    print(f"\n(for reference: model given the right version directly → {g['answer'][:80]!r} correct: {g['correct']})")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--qid"); ap.add_argument("--list", action="store_true"); ap.add_argument("--top", type=int, default=8)
    a = ap.parse_args()
    if a.list or not a.qid:
        ranked = sorted(run, key=score, reverse=True)[: a.top]
        for q in ranked:
            r = run[q]; print(f"{score(q)}  {q:28s} B:{'wrong' if not r['conds']['B_current']['correct'] else 'ok':5s} A:{'wrong' if not r['conds']['A_compressed']['correct'] else 'ok':5s} panelA:{''.join(v[0] for v in panel(q,'A_compressed').values())} D:{'ok' if resolved[q]['correct'] else 'wrong'}  gold={cases[q]['canonical_answer'][:45]}")
    if a.qid:
        show(a.qid)
