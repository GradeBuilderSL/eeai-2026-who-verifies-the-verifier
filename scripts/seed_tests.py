"""Seed tests on the injected qualifier-drop set (idea 7 as prerequisite for ideas 2 and 4).

Per case, one verifier (default gpt-5.4-mini), same H1 prompt:
  naive     = judge(false_claim, corrupted intermediate)   -> failure if "supported"
  anchored  = judge(false_claim, original)                 -> correct if "unsupported"
  ctrl_c    = judge(true_claim, corrupted)                 -> sanity
  ctrl_o    = judge(true_claim, original)                  -> sanity (expect supported)
  d_flip    = greedy deletion of restriction spans from the original, claim-overlap order,
              until the false claim is accepted; re-add pass; censored if never.
"""
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import make_model, verdict  # noqa: E402

SEED_FILE = Path(__file__).parent / "seed-qualifier-drop.json"  # overridable with --seed-file
def question(case: dict) -> str:
    return (f"Today is {case['as_of']}. Is the claim, read as a statement about today, supported by the evidence? "
            "Preserve conditions, time intervals, effective dates, cancellations and scope. "
            "Any unsupported assertion makes it unsupported.")
MAX_DFLIP_CALLS = 6


def render(case: dict, deleted: set) -> str:
    text = "".join(s["text"] for i, s in enumerate(case["segments"]) if i not in deleted)
    return text.replace(" .", ".").replace("  ", " ").replace(" ;", ";").replace(";.", ".").strip()


def dflip(model, case: dict) -> dict:
    spans = case["spans"]
    # Guard: a span whose content the claim relies on may not be deleted (that would make the
    # claim unsupported for a legitimate reason). Candidates = spans with no content-word overlap
    # with the claim, in text order. The critical restriction never overlaps by construction.
    # All marked restriction spans, in text order (the authoring spec guarantees the claim does not
    # depend on the decoy); the re-add pass below keeps only the deletions that are needed.
    order = list(range(len(spans)))
    deleted, calls, trace, flipped = [], 0, [], False
    for k in order:
        if calls >= MAX_DFLIP_CALLS:
            break
        deleted.append(spans[k]["index"])
        v = verdict(model, question(case), case["false_claim"], render(case, set(deleted)))
        calls += 1
        trace.append({"deleted": [case["segments"][i]["text"] for i in deleted], "verdict": v["verdict"], "reason": v["reason"][:160]})
        if v["verdict"] == "supported":
            flipped = True
            break
    if flipped and len(deleted) > 1:
        for d in list(deleted):
            if calls >= MAX_DFLIP_CALLS + 2:
                break
            trial = [x for x in deleted if x != d]
            v = verdict(model, question(case), case["false_claim"], render(case, set(trial)))
            calls += 1
            if v["verdict"] == "supported":
                deleted = trial
    critical = {s["index"] for s in spans if s["critical"]}
    return {"flipped": flipped, "d_flip": len(deleted) if flipped else None, "censored_at": None if flipped else len(deleted),
            "n_candidates": len(order),
            "critical_in_witness": critical.issubset(deleted) if flipped else None,
            "witness_is_exactly_critical": (set(deleted) == critical) if flipped else None, "calls": calls, "trace": trace}


def main(model_name: str, run_id: str, limit: int | None, provider: str = "openai", judges_only: bool = False, seed_file: Path = SEED_FILE) -> None:
    cases = [c for c in json.loads(seed_file.read_text(encoding="utf-8")) if "invalid" not in c]
    if limit:
        cases = cases[:limit]
    import common
    common.MODEL = model_name
    model, budget = make_model(run_id, max_calls=len(cases) * (4 + MAX_DFLIP_CALLS + 2) + 2,
                               db_path=Path(__file__).parent / f"{run_id}.sqlite", provider=provider)
    rows = []
    for c in cases:
        r = {"id": c["id"], "family": c["family"]}
        r["naive"] = verdict(model, question(c), c["false_claim"], c["corrupted"])["verdict"]
        r["anchored"] = verdict(model, question(c), c["false_claim"], c["original"])["verdict"]
        if judges_only:
            r["ctrl_c"] = r["ctrl_o"] = "skipped"; r["dflip"] = {"skipped": "judges_only"}
        else:
            r["ctrl_c"] = verdict(model, question(c), c["true_claim"], c["corrupted"])["verdict"]
            r["ctrl_o"] = verdict(model, question(c), c["true_claim"], c["original"])["verdict"]
            r["dflip"] = dflip(model, c) if r["anchored"] == "unsupported" else {"skipped": "anchored did not reject"}
        rows.append(r)
        print(c["id"], c["family"], "naive", r["naive"], "anchored", r["anchored"], "ctrl", r["ctrl_c"], r["ctrl_o"],
              "d_flip", r["dflip"].get("d_flip"), "censored", r["dflip"].get("censored_at"), flush=True)
    fam = sorted(set(r["family"] for r in rows))
    summary = {
        "model": model_name, "n": len(rows),
        "naive_accepts_false_claim": sum(r["naive"] == "supported" for r in rows),
        "anchored_accepts_false_claim": sum(r["anchored"] == "supported" for r in rows),
        "anchored_rejects": sum(r["anchored"] == "unsupported" for r in rows),
        "ctrl_true_claim_supported_on_original": sum(r["ctrl_o"] == "supported" for r in rows),
        "ctrl_true_claim_on_corrupted": dict(Counter(r["ctrl_c"] for r in rows)),
        "by_family": {f: {"naive_accept": sum(r["naive"] == "supported" for r in rows if r["family"] == f),
                          "anchored_reject": sum(r["anchored"] == "unsupported" for r in rows if r["family"] == f),
                          "d_flip": [r["dflip"].get("d_flip") for r in rows if r["family"] == f]} for f in fam},
        "d_flip_distribution": dict(Counter(str(r["dflip"].get("d_flip")) for r in rows if "d_flip" in r["dflip"])),
        "d_flip_censored": sum(1 for r in rows if r["dflip"].get("censored_at") is not None),
        "critical_span_in_witness": sum(1 for r in rows if r["dflip"].get("critical_in_witness")),
        "total_calls": 4 * len(rows) + sum(r["dflip"].get("calls", 0) for r in rows),
    }
    (Path(__file__).parent / f"{run_id}.json").write_text(json.dumps({"summary": summary, "rows": rows}, indent=2, ensure_ascii=False))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="gpt-5.4-mini-2026-03-17"); ap.add_argument("--run-id", default="seed-mini-20260921")
    ap.add_argument("--limit", type=int, default=None); ap.add_argument("--provider", default="openai")
    ap.add_argument("--judges-only", action="store_true"); ap.add_argument("--seed-file", default=str(SEED_FILE))
    a = ap.parse_args(); main(a.model, a.run_id, a.limit, a.provider, a.judges_only, Path(a.seed_file))
