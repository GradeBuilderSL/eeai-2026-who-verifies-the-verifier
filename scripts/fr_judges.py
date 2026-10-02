"""Extra judges over the stored fiscal-fr-bench answers: GPT-5.4 and DeepSeek verify each answer against the same
evidence condition it came from; merged with mini's verdicts → unanimity vs correctness on real degraded evidence."""
import argparse
import json
import sys
from collections import Counter
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import common  # noqa: E402
from common import make_model, verdict  # noqa: E402

SCRIPTS = Path(__file__).resolve().parent
# Inputs and outputs live in one working folder (default ../work, built by prepare_work.py); override with WVV_WORK.
HERE = Path(os.environ.get("WVV_WORK", str(SCRIPTS.parent / "work")))
JUDGES = {"gpt54": ("gpt-5.4-2026-03-05", "openai"), "deepseek": ("deepseek-flash", "deepseek")}


def main(stage: str) -> None:
    cases = {c["qid"]: c for c in json.loads((HERE / CASES_FILE).read_text(encoding="utf-8"))}
    mini = json.loads((HERE / RUN_FILE).read_text(encoding="utf-8"))
    if stage == "judge":
        # the compressed text is not stored; reconstruct evidence for B and C only, and A from the mini run if present
        for jname, (mid, prov) in JUDGES.items():
            common.MODEL = mid
            model, _ = make_model(f"fr-judge-{jname}{TAG}-20260921", max_calls=len(mini["rows"]) * 3 + 2, db_path=HERE / f"fr-judge-{jname}{TAG}.sqlite", provider=prov)
            out = []
            for r in mini["rows"]:
                c = cases[r["qid"]]
                ev = {"A_compressed": r.get("compressed_text"), "B_current": c["current_text"], "C_gold": c["gold_text"]}
                row = {"qid": r["qid"], "conds": {}}
                for name, x in r["conds"].items():
                    if not x.get("answer") or not ev.get(name):
                        row["conds"][name] = "n/a"; continue
                    q = f"Date de référence : {c['date_anchor']}. La réponse est-elle étayée par les éléments fournis pour cette date ? Conserver les dates d'entrée en vigueur, les versions et les seuils."
                    row["conds"][name] = verdict(model, q, x["answer"], ev[name])["verdict"]
                out.append(row); print(jname, r["qid"], row["conds"], flush=True)
            (HERE / f"fr-judge-{jname}{TAG}-20260921.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))
        return
    judges = {"mini": {r["qid"]: {k: v["verifier"] for k, v in r["conds"].items()} for r in mini["rows"]}}
    for jname in JUDGES:
        p = HERE / f"fr-judge-{jname}{TAG}-20260921.json"
        if p.exists():
            judges[jname] = {r["qid"]: r["conds"] for r in json.loads(p.read_text(encoding="utf-8"))}
    correct = {r["qid"]: {k: v["correct"] for k, v in r["conds"].items()} for r in mini["rows"]}
    report = {}
    for name in ("A_compressed", "B_current", "C_gold"):
        unan = unan_wrong = unan_right = n = 0; per = Counter()
        for qid in correct:
            vs = [judges[j].get(qid, {}).get(name) for j in judges]
            if any(v in (None, "n/a") for v in vs):
                continue
            n += 1
            for j, v in zip(judges, vs):
                per[j] += (v == "supported")
            if len(set(vs)) == 1 and vs[0] in ("supported", "unsupported"):
                unan += 1
                if vs[0] == "supported" and not correct[qid][name]:
                    unan_wrong += 1
                if vs[0] == "supported" and correct[qid][name]:
                    unan_right += 1
        report[name] = {"n": n, "judges": list(judges), "unanimous": unan, "unanimous_accept_of_WRONG_answer": unan_wrong,
                        "unanimous_accept_of_right_answer": unan_right, "accepts_per_judge": dict(per),
                        "wrong_answers": sum(1 for q in correct if not correct[q][name])}
    (HERE / f"fr-judges-merged{TAG}.json").write_text(json.dumps(report, indent=1))
    print(json.dumps(report, indent=1))


RUN_FILE, CASES_FILE, TAG = "fr-mini-20260921.json", "fr-cases.json", ""

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("stage", choices=["judge", "merge"])
    ap.add_argument("--run-file", default=RUN_FILE); ap.add_argument("--cases", default=CASES_FILE); ap.add_argument("--tag", default="")
    a = ap.parse_args(); RUN_FILE, CASES_FILE, TAG = a.run_file, a.cases, a.tag
    JUDGES.update({"mini": ("gpt-5.4-mini-2026-03-17", "openai")} if a.tag else {})
    main(a.stage)
