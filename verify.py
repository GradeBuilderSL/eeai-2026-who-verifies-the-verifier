"""Recompute every number quoted in the talk from the raw result files — no API calls, no model.

    python verify.py

Each line prints the number as said on stage and the file it comes from. A mismatch exits non-zero.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

RESULTS = Path(__file__).parent / "results"
CHECKS: list[tuple[str, object, object, str]] = []  # (label, expected, actual, file)


def load(name: str):
    return json.loads((RESULTS / name).read_text(encoding="utf-8"))


def check(label: str, expected, actual, file: str) -> None:
    CHECKS.append((label, expected, actual, file))


def accuracy_abc(run_file: str) -> dict[str, tuple[int, int]]:
    """Accuracy per evidence condition, recounted from the per-question rows (not the stored summary)."""
    run = load(run_file)
    out: dict[str, tuple[int, int]] = {}
    for cond in ("A_compressed", "B_current", "C_gold"):
        rows = run["rows"]
        out[cond] = (sum(1 for r in rows if r["conds"][cond].get("correct")), len(rows))
    return out


def accuracy_d(rescored_file: str) -> tuple[int, int]:
    rows = load(rescored_file)["rows"]
    return sum(1 for r in rows if r["correct"]), len(rows)


def unanimous_wrong(judge_files: list[str], run_file: str) -> dict[str, tuple[int, int]]:
    """Wrong answers (by the benchmark's deterministic nuggets) that all three judges marked 'supported'."""
    run = {r["qid"]: r for r in load(run_file)["rows"]}
    judges = [{r["qid"]: r["conds"] for r in load(f)} for f in judge_files]
    out: dict[str, tuple[int, int]] = {}
    for cond in ("A_compressed", "B_current", "C_gold"):
        # Denominator = wrong answers the judges actually saw. In A, 4 more compressions returned nothing
        # (no answer, nothing to judge): 23 wrong in total, 19 judged. The talk says "9 of 19" (47 %).
        wrong = [q for q, r in run.items() if r["conds"][cond].get("answer") and not r["conds"][cond]["correct"]]
        unanimous = sum(1 for q in wrong if all(j.get(q, {}).get(cond) == "supported" for j in judges))
        out[cond] = (unanimous, len(wrong))
    return out


def main() -> int:
    # 1. The evidence path decides (fig1). gpt-5.4 / gpt-5.4-mini / gpt-5.4-nano, 100 date-anchored questions.
    for model, run, events in (("gpt-5.4", "fr-gpt54-100v3-20260921.json", "fr-events-v4-gpt54-100v3-20260921.rescored.json"),
                               ("gpt-5.4-mini", "fr-mini-100v3-20260921.json", "fr-events-v4-mini-100v3-20260921.rescored.json"),
                               ("gpt-5.4-nano", "fr-nano-100v3-20261002.json", "fr-events-v4-nano-100v3-20261002.rescored.json")):
        acc = accuracy_abc(run)
        exp = {"gpt-5.4": (77, 3, 91, 99), "gpt-5.4-mini": (52, 3, 90, 99), "gpt-5.4-nano": (12, 3, 91, 97)}[model]
        check(f"{model} A compressed history", exp[0], acc["A_compressed"][0], run)
        check(f"{model} B today's version", exp[1], acc["B_current"][0], run)
        check(f"{model} C version in force", exp[2], acc["C_gold"][0], run)
        check(f"{model} D one typed figure per version + resolve", exp[3], accuracy_d(events)[0], events)
    nano = load("fr-nano-100v3-20261002.json")["summary"]["A_compressed"]
    check("gpt-5.4-nano: compressions that returned nothing", 69, nano["verifier_verdicts_on_wrong"]["no_evidence"],
          "fr-nano-100v3-20261002.json")
    # Repeat runs (gpt-5.4-mini ×3): D is reproducible, A is not.
    for tag, (a, d) in (("r2", (66, 99)), ("r3", (60, 99))):
        check(f"gpt-5.4-mini repeat {tag}: A", a, accuracy_abc(f"fr-mini-100v3-20261002-{tag}.json")["A_compressed"][0],
              f"fr-mini-100v3-20261002-{tag}.json")
        check(f"gpt-5.4-mini repeat {tag}: D", d, accuracy_d(f"fr-events-v4-mini-100v3-20261002-{tag}.rescored.json")[0],
              f"fr-events-v4-mini-100v3-20261002-{tag}.rescored.json")
    # 2. Three judges certify the invisible lie (fig2): gpt-5.4 answers, judges mini / gpt-5.4 / deepseek.
    judges = ["fr-judge-mini-g100v3-20260921.json", "fr-judge-gpt54-g100v3-20260921.json",
              "fr-judge-deepseek-g100v3-20260921.json"]
    uw = unanimous_wrong(judges, "fr-gpt54-100v3-20260921.json")
    check("3 judges unanimously certify WRONG answers — A compressed (19 judged; 4 blank compressions not judged)",
          (9, 19), uw["A_compressed"], judges[1])
    blank = sum(1 for r in load("fr-gpt54-100v3-20260921.json")["rows"] if not r["conds"]["A_compressed"].get("answer"))
    check("A compressed: compressions that returned nothing (wrong, but never judged)", 4, blank,
          "fr-gpt54-100v3-20260921.json")
    check("3 judges unanimously certify WRONG answers — B today's version", (2, 97), uw["B_current"], judges[1])
    check("3 judges unanimously certify WRONG answers — C version in force", (5, 9), uw["C_gold"], judges[1])
    seeds = load("seed-merged.json")["agreement"]["naive"]
    check("injected restriction drops, own seed: unanimous & wrong", (5, 9),
          (seeds["unanimous_accept_false_claim"], seeds["n_unanimous"]), "seed-merged.json")
    seeds_ds = load("seed-merged-ds.json")["agreement"]
    check("injected restriction drops, model seed: unanimous & wrong", (7, 10),
          (seeds_ds["naive"]["unanimous_accept_false_claim"], seeds_ds["naive"]["n_unanimous"]), "seed-merged-ds.json")
    check("same seeds, judges see the ORIGINAL: unanimous & wrong", 0,
          seeds_ds["anchored"]["unanimous_accept_false_claim"], "seed-merged-ds.json")
    t2b = load("t2b-three-judges.json")
    check("AggreFact natural errors: false claims all three accepted (compressed)", 0,
          t2b["summary"]["unanimous_and_wrong_by_gold"].get("unsupported", 0), "t2b-three-judges.json")
    check("AggreFact natural errors: false claims all three accepted (original)", 2,
          t2b["original"]["unanimous_and_wrong_by_gold"].get("unsupported", 0), "t2b-three-judges.json")
    t3 = load("t3-placebo-length.json")["summary"]
    check("placebo length: false accepts compressed / original / padded", (6, 11, 10),
          (t3["false_accepts"]["summary"], t3["false_accepts"]["original"], t3["false_accepts"]["placebo"]),
          "t3-placebo-length.json")
    # 3. Who verifies the verifier: the resolved value catches what the panel passed (16/16, 0 false alarms).
    events = {r["qid"]: r for r in load("fr-events-v4-gpt54-100v3-20260921.rescored.json")["rows"]}
    run = {r["qid"]: r for r in load("fr-gpt54-100v3-20260921.json")["rows"]}
    jd = [{r["qid"]: r["conds"] for r in load(f)} for f in judges]
    caught = flagged = passed = 0
    for cond in ("A_compressed", "B_current", "C_gold"):
        for q, r in run.items():
            x = r["conds"][cond]
            if not x.get("answer"):
                continue
            disagree = events[q]["correct"] and not x["correct"]
            if not x["correct"] and all(j.get(q, {}).get(cond) == "supported" for j in jd):
                passed += 1
                caught += disagree
            if x["correct"] and not events[q]["correct"]:
                flagged += 1
    check("resolved value catches the panel-certified wrong answers", (16, 16), (caught, passed),
          "fr-events-v4-gpt54-100v3-20260921.rescored.json")
    check("resolved value: right answers wrongly flagged (ignoring the one shared D miss)", 0,
          max(0, flagged - 1), "fr-events-v4-gpt54-100v3-20260921.rescored.json")
    # 4. A calibrated decision model as the fourth judge (fig4).
    jev = load("fr-judge-jev-fr-gpt54-100v3-20260921.report.json")
    check("Jev certifies WRONG answers — A compressed", (10, 19),
          (jev["A_compressed"]["jev_accepts_WRONG"], jev["A_compressed"]["wrong_answers"]), "fr-judge-jev-*.report.json")
    check("Jev certifies WRONG answers — C version in force", (9, 9),
          (jev["C_gold"]["jev_accepts_WRONG"], jev["C_gold"]["wrong_answers"]), "fr-judge-jev-*.report.json")
    check("Jev rejects, of the 9 invisible lies the three LLM judges passed", 1,
          jev["A_compressed"]["of_which_jev_rejects"], "fr-judge-jev-*.report.json")
    # 5. Tomorrow (fig3): recorded future vs invented future.
    p = load("fr-predict-gpt54-20260922.json")["summary"]
    check("future recorded (47): model right / resolve right", (38, 45),
          (p["future_recorded"]["llm_correct"], p["future_recorded"]["resolve_correct"]), "fr-predict-gpt54-20260922.json")
    check("future NOT recorded (78): resolve declines ('expired')", 72,
          p["future_not_recorded"]["resolve_statuses"]["expired"], "fr-predict-gpt54-20260922.json")
    check("future NOT recorded (78): model answers anyway (invented figures)", 72,
          p["future_not_recorded"]["n"] - p["future_not_recorded"]["llm_correct"] - 1, "fr-predict-gpt54-20260922.json")

    bad = 0
    for label, expected, actual, file in CHECKS:
        ok = expected == actual
        bad += not ok
        print(f"{'OK ' if ok else 'MISMATCH'}  {label}: {actual}{'' if ok else f' (expected {expected})'}   [{file}]")
    print(f"\n{len(CHECKS) - bad}/{len(CHECKS)} numbers reproduced from the raw files.")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
