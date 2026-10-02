"""Condition D v4 — per-version extraction, deterministic time.

The history is already segmented by version headers carrying validity dates. The model is asked ONE question per
version: "what value does the question ask about, in THIS version?" (number + unit, or null). Code assigns
effective_at / expires from the headers, writes adopt/replace events in order, and `resolve` returns the value in
force on the question's date. The model never handles dates; the journal owns time — the architecture's claim.
"""
import argparse
import json
import re
import sys
import os
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
# Inputs and outputs live in one working folder (default ../work, built by prepare_work.py); override with WVV_WORK.
HERE = Path(os.environ.get("WVV_WORK", str(SCRIPTS.parent / "work")))
sys.path.insert(0, str(SCRIPTS))
import common  # noqa: E402
from common import make_model  # noqa: E402
from fr_run import strict  # noqa: E402
from project_memory.language import ModelRequest  # noqa: E402
from project_memory.models import canonical  # noqa: E402
from t4_events import project  # noqa: E402

HDR = re.compile(r"\[Article (.+?) — version en vigueur du (\S+) au (.+?)\]\n")
INSTR = """La question demande une valeur précise (seuil, taux, montant, durée). Le texte est UNE version d'un article.
Réponds UNIQUEMENT en JSON {"value": "le chiffre demandé avec son unité, tel qu'écrit (ex. '61 634 €', '33 1/3 %', '5 ans')" ou null}.
null si cette version ne contient pas la valeur demandée. Aucune connaissance extérieure, aucune phrase."""


def split_versions(history: str) -> list[dict]:
    parts = HDR.split(history)
    out = []
    for i in range(1, len(parts), 4):
        num, d0, d1, text = parts[i], parts[i + 1], parts[i + 2], parts[i + 3]
        out.append({"num": num, "start": d0, "end": None if d1 == "en cours" else d1, "text": text.strip()})
    return out


def main(model_name: str, provider: str, run_id: str, cases_file: str, limit: int | None) -> None:
    cases = json.loads((HERE / cases_file).read_text(encoding="utf-8"))
    if limit:
        cases = cases[:limit]
    n_calls = sum(len(split_versions(c["history_text"])) for c in cases)
    common.MODEL = model_name
    model, _ = make_model(run_id, max_calls=n_calls + 2, db_path=HERE / f"{run_id}.sqlite", provider=provider, output_per_call=120)
    rows = []
    for c in cases:
        versions = split_versions(c["history_text"])
        events, prev, errs = [], None, 0
        for v in versions:
            if v["start"] == "?":
                continue
            req = ModelRequest("fr_value", INSTR, canonical({"question": c["prompt"], "texte": v["text"]}), 60000, 120, version="smoke-fr-events-v4.v1")
            try:
                resp = model.complete(req); val = json.loads(resp.output).get("value")
            except Exception:
                errs += 1; val = None
            if val:
                ev = {"kind": "replace" if prev is not None else "adopt", "value": str(val), "effective_at": v["start"], "expires": v["end"], "targets": [prev] if prev is not None else []}
                events.append(ev); prev = len(events) - 1
        status, value, err = project(events, c["date_anchor"]) if events else ("no_events", None, "")
        answer = f"Article {c['article_num']} : {value}" if value else ""
        ok = strict(c["nuggets"], answer) if answer else False
        rows.append({"qid": c["qid"], "n_versions": len(versions), "events": events, "resolved": {"status": status, "value": value}, "answer": answer, "correct": ok, "call_errors": errs, "error": err})
        print(c["qid"], "versions", len(versions), "events", len(events), "status", status, "value", value, "OK" if ok else "wrong", flush=True)
    summ = {"model": model_name, "n": len(rows), "accuracy": f"{sum(r['correct'] for r in rows)}/{len(rows)}",
            "resolved_active": sum(r["resolved"]["status"] == "active" for r in rows), "unknown": sum(r["resolved"]["status"] == "unknown" for r in rows),
            "call_errors": sum(r["call_errors"] for r in rows), "calls": n_calls}
    (HERE / f"{run_id}.json").write_text(json.dumps({"summary": summ, "rows": rows}, indent=1, ensure_ascii=False))
    print(json.dumps(summ, indent=1))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--model", default="gpt-5.4-mini-2026-03-17"); ap.add_argument("--provider", default="openai")
    ap.add_argument("--run-id", default="fr-events-v4-mini-20260921"); ap.add_argument("--cases", default="fr-cases-v2.json"); ap.add_argument("--limit", type=int, default=None)
    a = ap.parse_args(); main(a.model, a.provider, a.run_id, a.cases, a.limit)
