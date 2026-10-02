"""Predictive advice from recorded history: LLM vs resolve.

Pairs of killer questions on the same article with anchors d1 < d2. From the vantage of d1 (history window built
around d1), answer question 2 (about d2): (a) the model reads the FULL history and answers; (b) `resolve` on d2
over the events extracted per version from that same history (D v4, stored). Scored with question 2's nuggets.
Split by whether the version in force on d2 is inside the d1 window ("future recorded") or not.
"""
import argparse
import json
import re
import sys
from collections import Counter
import os
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
# Inputs and outputs live in one working folder (default ../work, built by prepare_work.py); override with WVV_WORK.
HERE = Path(os.environ.get("WVV_WORK", str(SCRIPTS.parent / "work")))
sys.path.insert(0, str(SCRIPTS))
import common  # noqa: E402
from common import make_model  # noqa: E402
from fr_run import strict  # noqa: E402
from fr_events_rescore import project_fixed, fix_thousands  # noqa: E402
from project_memory.language import ModelRequest  # noqa: E402
from project_memory.models import canonical  # noqa: E402

HDR = re.compile(r"\[Article (.+?) — version en vigueur du (\S+) au (.+?)\]")
ANSWER = """Réponds à la question en te fondant UNIQUEMENT sur l'historique de versions fourni (aucune connaissance extérieure).
La question porte sur une date précise ; donne la valeur qui s'appliquera à cette date d'après l'historique, et le numéro
d'article, en une ou deux phrases en français. Réponds UNIQUEMENT en JSON {"answer": string}."""


def pairs(cases):
    by_art = {}
    for c in cases:
        by_art.setdefault(c["article_num"], []).append(c)
    out = []
    for art, cs in by_art.items():
        cs = sorted(cs, key=lambda c: c["date_anchor"])
        for i in range(len(cs)):
            for j in range(i + 1, len(cs)):
                out.append((cs[i], cs[j]))
    return out


def recorded(c1, c2):
    g = HDR.search(c2["gold_text"])
    return g is not None and g.group(2) in [m[1] for m in HDR.findall(c1["history_text"])]


def main(model_name, provider, run_id):
    cases = json.loads((HERE / "fr-cases-100-v3.json").read_text(encoding="utf-8"))
    events = {r["qid"]: r["events"] for r in json.loads((HERE / "fr-events-v4-gpt54-100v3-20260921.json").read_text(encoding="utf-8"))["rows"]}
    ps = pairs(cases)
    common.MODEL = model_name
    model, _ = make_model(run_id, max_calls=len(ps) + 2, db_path=HERE / f"{run_id}.sqlite", provider=provider, output_per_call=400)
    rows = []
    for c1, c2 in ps:
        req = ModelRequest("fr_predict", ANSWER, canonical({"question": c2["prompt"], "date": c2["date_anchor"], "historique": c1["history_text"]}), 60000, 400, version="smoke-fr-predict.v1")
        try:
            ans = json.loads(model.complete(req).output).get("answer") or ""
        except Exception as exc:
            ans = ""
        llm_ok = strict(c2["nuggets"], ans) if ans else False
        status, value, err = project_fixed(events[c1["qid"]], c2["date_anchor"]) if events.get(c1["qid"]) else ("no_events", None, "")
        r_ans = f"Article {c2['article_num']} : {fix_thousands(value)}" if value else ""
        res_ok = strict(c2["nuggets"], r_ans) if r_ans else False
        rec = recorded(c1, c2)
        rows.append({"from": c1["qid"], "to": c2["qid"], "future_recorded": rec, "llm_answer": ans[:200], "llm_correct": llm_ok,
                     "resolve": {"status": status, "value": value}, "resolve_correct": res_ok})
        print(c1["qid"][6:], "->", c2["date_anchor"], "recorded", rec, "LLM", "OK" if llm_ok else "wrong", "| resolve", status, value, "OK" if res_ok else "wrong", flush=True)
    summ = {"model": model_name, "pairs": len(rows)}
    for rec in (True, False):
        sub = [r for r in rows if r["future_recorded"] == rec]
        summ["future_recorded" if rec else "future_not_recorded"] = {"n": len(sub), "llm_correct": sum(r["llm_correct"] for r in sub), "resolve_correct": sum(r["resolve_correct"] for r in sub),
                                                                    "resolve_statuses": dict(Counter(r["resolve"]["status"] for r in sub))}
    (HERE / f"{run_id}.json").write_text(json.dumps({"summary": summ, "rows": rows}, indent=1, ensure_ascii=False))
    print(json.dumps(summ, indent=1))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--model", default="gpt-5.4-mini-2026-03-17"); ap.add_argument("--provider", default="openai"); ap.add_argument("--run-id", default="fr-predict-mini-20260922")
    a = ap.parse_args(); main(a.model, a.provider, a.run_id)
