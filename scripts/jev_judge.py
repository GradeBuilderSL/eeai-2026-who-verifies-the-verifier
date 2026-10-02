"""Jev (TypeSafe System-One, calibrated decision model) as a FOURTH judge over the stored fiscal-fr-bench answers.

Same question and evidence as the three LLM judges (fr_judges.py): for each stored answer under each evidence
condition (A compressed / B current / C as-of), ask Jev a Choice over {supported, unsupported, uncertain}.
Jev returns a typed choice with a probability per option — so we also get a calibration check against the
benchmark's deterministic gold (is P(supported) honest when the answer is wrong?).

Key: TYPESAFE_API_KEY in the environment (run_with_keys.py injects it from the owner's .env; never printed).
Run:  python run_with_keys.py jev_judge.py judge --run-file fr-gpt54-100v3-20260921.json --cases fr-cases-100-v3.json [--limit N]
      python run_with_keys.py jev_judge.py report --run-file fr-gpt54-100v3-20260921.json --cases fr-cases-100-v3.json
Prices (02.10.2026): $0.042 per million input tokens, output free; the whole run (≈300 verdicts × ≤25k chars) is cents.
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

import httpx

SCRIPTS = Path(__file__).resolve().parent
# Inputs and outputs live in one working folder (default ../work, built by prepare_work.py); override with WVV_WORK.
HERE = Path(os.environ.get("WVV_WORK", str(SCRIPTS.parent / "work")))
ENDPOINT = os.environ.get("TYPESAFE_ENDPOINT", "https://api.typesafe.ai/v1/systemone")
MODEL = os.environ.get("TYPESAFE_MODEL", "jev-latest")
OPTIONS = {
    "supported": "La réponse est étayée par les éléments fournis POUR LA DATE DE RÉFÉRENCE : la version en vigueur à "
                 "cette date, ses seuils, taux, montants et dates d'entrée en vigueur confirment la valeur donnée.",
    "unsupported": "La réponse n'est pas étayée : la valeur donnée ne figure pas pour cette date, ou elle correspond "
                   "à une autre version (antérieure ou postérieure), ou elle élargit/ignore une condition, une date "
                   "d'entrée en vigueur, une négation ou une restriction.",
    "uncertain": "Les éléments fournis ne permettent pas de trancher.",
}


def ask(client: httpx.Client, key: str, state: str, question: str) -> dict:
    # Native API (docs.typesafe.ai): state is an object; answers.<name>.choice / confidence / probabilities.
    body = {"model": MODEL, "state": {"elements_fournis": state},
            "questions": {"verdict": {"type": "choice", "instructions": question, "criteria": OPTIONS}}}
    for attempt in range(4):
        try:
            r = client.post(ENDPOINT, headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                            json=body, timeout=60)
        except httpx.HTTPError as exc:
            if attempt == 3:
                return {"error": type(exc).__name__}
            time.sleep(2 * (attempt + 1)); continue
        if r.status_code in (429, 500, 502, 503) and attempt < 3:
            time.sleep(2 * (attempt + 1)); continue
        if r.status_code != 200:
            return {"error": f"http {r.status_code}", "body": r.text[:300]}
        data = r.json()
        ans = (data.get("answers") or data.get("results") or {}).get("verdict") or {}
        choice = ans.get("choice") or ans.get("answer") or ans.get("value")
        probs = ans.get("probabilities") or ans.get("distribution") or ans.get("scores") or {}
        conf = ans.get("confidence")
        return {"verdict": choice, "confidence": conf, "probabilities": probs, "raw": data,
                "input_tokens": (data.get("usage") or {}).get("input_tokens")}
    return {"error": "exhausted"}


def judge(run_file: str, cases_file: str, limit: int | None) -> None:
    key = os.environ.get("TYPESAFE_API_KEY") or os.environ.get("PROJECT_MEMORY_TYPESAFE_API_KEY")
    if not key:
        sys.exit("TYPESAFE_API_KEY is not set (put it into the owner's .env; run via run_with_keys.py)")
    cases = {c["qid"]: c for c in json.loads((HERE / cases_file).read_text(encoding="utf-8"))}
    run = json.loads((HERE / run_file).read_text(encoding="utf-8"))
    rows = run["rows"][:limit] if limit else run["rows"]
    out_path = HERE / f"fr-judge-jev-{Path(run_file).stem}.json"
    out = json.loads(out_path.read_text(encoding="utf-8")) if out_path.exists() else []
    done = {r["qid"] for r in out}
    with httpx.Client() as client:
        for r in rows:
            if r["qid"] in done:
                continue
            c = cases[r["qid"]]
            ev = {"A_compressed": r.get("compressed_text"), "B_current": c["current_text"], "C_gold": c["gold_text"]}
            row = {"qid": r["qid"], "conds": {}}
            for name, x in r["conds"].items():
                if not x.get("answer") or not ev.get(name):
                    row["conds"][name] = {"verdict": "n/a"}; continue
                q = (f"Date de référence : {c['date_anchor']}. Question : {c['prompt']} Réponse proposée : {x['answer']} "
                     "— cette réponse est-elle étayée par les éléments fournis pour cette date ? Conserver les dates "
                     "d'entrée en vigueur, les versions et les seuils.")
                state = f"ÉLÉMENTS FOURNIS (texte juridique, versions datées) :\n{ev[name]}"
                res = ask(client, key, state, q)
                row["conds"][name] = {**res, "correct": x["correct"]}
            out.append(row)
            out_path.write_text(json.dumps(out, indent=1, ensure_ascii=False))
            print(r["qid"], {k: (v.get("verdict"), v.get("confidence"), "OK" if v.get("correct") else "wrong")
                             for k, v in row["conds"].items()}, flush=True)
    print("saved", out_path)


def report(run_file: str, cases_file: str) -> None:
    jev = json.loads((HERE / f"fr-judge-jev-{Path(run_file).stem}.json").read_text(encoding="utf-8"))
    run = json.loads((HERE / run_file).read_text(encoding="utf-8"))
    # The three LLM judges over the same stored answers (fr_judges.py, tag g100v3): mini, gpt-5.4, deepseek.
    others = {}
    for jname in ("gpt54", "deepseek"):
        p = HERE / f"fr-judge-{jname}-g100v3-20260921.json"
        if p.exists():
            others[jname] = {r["qid"]: r["conds"] for r in json.loads(p.read_text(encoding="utf-8"))}
    mini_file = HERE / "fr-judge-mini-g100v3-20260921.json"
    mini = ({r["qid"]: r["conds"] for r in json.loads(mini_file.read_text(encoding="utf-8"))} if mini_file.exists()
            else {r["qid"]: {k: v["verifier"] for k, v in r["conds"].items()} for r in run["rows"]})
    rep = {}
    for name in ("A_compressed", "B_current", "C_gold"):
        n = wrong = jev_acc_wrong = jev_acc_right = right = 0
        panel_unan_wrong = 0; jev_catches_panel = 0; bins = {}
        for r in jev:
            x = r["conds"].get(name) or {}
            if x.get("verdict") in (None, "n/a") or "error" in x:
                continue
            n += 1
            p_sup = (x.get("probabilities") or {}).get("supported")
            if p_sup is None and x.get("verdict") == "supported":
                p_sup = x.get("confidence")
            if x["correct"]:
                right += 1; jev_acc_right += x["verdict"] == "supported"
            else:
                wrong += 1; jev_acc_wrong += x["verdict"] == "supported"
                vs = [mini.get(r["qid"], {}).get(name)] + [others[j].get(r["qid"], {}).get(name) for j in others]
                if len(others) == 2 and all(v == "supported" for v in vs):
                    panel_unan_wrong += 1
                    jev_catches_panel += x["verdict"] != "supported"
            if isinstance(p_sup, (int, float)):
                b = min(int(p_sup * 5), 4)
                bins.setdefault(b, [0, 0]); bins[b][0] += 1; bins[b][1] += int(x["correct"])
        rep[name] = {"n": n, "wrong_answers": wrong, "jev_accepts_WRONG": jev_acc_wrong, "right_answers": right,
                     "jev_accepts_right": jev_acc_right,
                     "wrong_answers_the_3_LLM_judges_unanimously_passed": panel_unan_wrong,
                     "of_which_jev_rejects": jev_catches_panel,
                     "calibration_bins_P(supported)->[n, n_correct]": {f"{b/5:.1f}-{(b+1)/5:.1f}": v for b, v in sorted(bins.items())}}
    (HERE / f"fr-judge-jev-{Path(run_file).stem}.report.json").write_text(json.dumps(rep, indent=1, ensure_ascii=False))
    print(json.dumps(rep, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("stage", choices=["judge", "report"])
    ap.add_argument("--run-file", default="fr-gpt54-100v3-20260921.json"); ap.add_argument("--cases", default="fr-cases-100-v3.json")
    ap.add_argument("--limit", type=int, default=None)
    a = ap.parse_args()
    (judge if a.stage == "judge" else lambda rf, cf, _l: report(rf, cf))(a.run_file, a.cases, a.limit)
