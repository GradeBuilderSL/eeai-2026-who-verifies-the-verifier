"""T3 — placebo-length control for H1 (idea 8 / Claude §7.4).

Third arm on the 32-family (64-claim) subset: the compressed text FIRST, then unrelated prose
from another family's article, padded to the length of this case's original. Same instructions,
same model (gpt-5.4-mini) as the primary run. Compared against the primary run's stored verdicts
for the summary and original arms on the same 64 claims.

Decision rule (pre-declared): if the placebo arm's false accepts on unsupported-gold claims are
within 1 of the original arm's (and clearly above the summary arm's), the H1 shift is explained
by context LENGTH, not by the content of the original. If placebo ~= summary arm, content matters.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import (SENS32, build_placebo, load_gold160, load_observations,  # noqa: E402
                    make_model, pick_by_hash, verdict)

SEED = "t3-placebo-20260921-v1"
OUT = Path(__file__).parent / "t3-placebo-length.json"


def fillers_for(case: dict, cases: list[dict]) -> list[str]:
    """Originals of OTHER families, in a deterministic per-case order."""
    others = [c for c in cases if c["material"]["scope"]["project"] != case["material"]["scope"]["project"]]
    order = pick_by_hash([c["id"] for c in others], SEED + ":" + case["id"], len(others))
    by_id = {c["id"]: c for c in others}
    return [by_id[i]["material"]["source"]["text"] for i in order]


def main(limit: int | None) -> None:
    cases = [json.loads(l) for l in SENS32.read_text(encoding="utf-8").splitlines() if l.strip()]
    cases.sort(key=lambda c: c["id"])
    if limit:
        cases = cases[:limit]
    gold, obs = load_gold160(), load_observations()
    model, budget = make_model("t3-placebo-20260921", max_calls=len(cases) + 2,
                               db_path=Path(__file__).parent / "t3-placebo.sqlite")
    rows = []
    for c in cases:
        summary, original = c["summary"], c["material"]["source"]["text"]
        placebo = build_placebo(summary, len(original), fillers_for(c, cases))
        v = verdict(model, c["question"], c["claim"], placebo)
        rows.append({
            "id": c["id"], "gold": gold[c["id"]],
            "summary_verdict": obs[c["id"]].get("summary"), "original_verdict": obs[c["id"]].get("original"),
            "placebo_verdict": v["verdict"], "placebo_reason": v["reason"],
            "len_summary": len(summary), "len_original": len(original), "len_placebo": len(placebo),
            "tokens": [v["input_tokens"], v["output_tokens"]],
        })
        print(c["id"], gold[c["id"]], "S", rows[-1]["summary_verdict"], "O", rows[-1]["original_verdict"], "P", v["verdict"], flush=True)

    def count(arm, g, val):
        return sum(1 for r in rows if r["gold"] == g and r[arm] == val)
    n_unsup = sum(1 for r in rows if r["gold"] == "unsupported")
    n_sup = sum(1 for r in rows if r["gold"] == "supported")
    summary = {
        "n": len(rows), "n_unsupported_gold": n_unsup, "n_supported_gold": n_sup,
        "false_accepts": {a: count(a + "_verdict", "unsupported", "supported") for a in ("summary", "original", "placebo")},
        "correct_accepts": {a: count(a + "_verdict", "supported", "supported") for a in ("summary", "original", "placebo")},
        "placebo_agrees_with": {
            "summary": sum(1 for r in rows if r["placebo_verdict"] == r["summary_verdict"]),
            "original": sum(1 for r in rows if r["placebo_verdict"] == r["original_verdict"]),
        },
        "errors": sum(1 for r in rows if r["placebo_verdict"] == "error"),
        "budget": budget.report() if hasattr(budget, "report") else None,
    }
    OUT.write_text(json.dumps({"seed": SEED, "summary": summary, "rows": rows}, indent=2, ensure_ascii=False))
    print(json.dumps(summary, indent=2, default=str))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--limit", type=int, default=None)
    main(ap.parse_args().limit)
