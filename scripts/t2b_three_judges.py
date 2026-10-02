"""T2b — three judges on IDENTICAL input (zero model calls).

On the 32-family / 64-claim subset, three verifiers (gpt-5.4-mini, gpt-5.4, deepseek-flash) saw
exactly the same evidence in each arm. Does unanimous agreement carry information about
correctness, and how often do all three accept the same false claim? (Idea 4; abstract's
"agreement is correlated rather than independent".)
"""
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import RUNS, load_gold160, load_observations  # noqa: E402

OUT = Path(__file__).parent / "t2b-three-judges.json"


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]


def verdict_map(rows: list[dict]) -> dict:
    out = {}
    for r in rows:
        cid = r.get("case_id") or r.get("id")
        v = r.get("outcome") or r.get("verdict")
        if cid and v:
            out[cid] = v
    return out


def main() -> None:
    gold = load_gold160()
    mini = load_observations()  # case_id -> {mode: outcome}
    judges = {}
    for name in ("gpt54", "deepseek"):
        d = RUNS / f"model-sensitivity-{name}-20260919"
        for mode in ("summary", "original"):
            rows = load_jsonl(d / f"observations.{mode}.neutral.jsonl")
            judges.setdefault(name, {})[mode] = verdict_map(rows)
            if not judges[name][mode]:
                print("UNEXPECTED ROW SHAPE", name, mode, list(rows[0].keys()) if rows else "empty")
    ids = sorted(set(judges["gpt54"]["summary"]) & set(judges["deepseek"]["summary"]))
    report = {"n": len(ids)}
    for mode in ("summary", "original"):
        trip = Counter(); unanimous = unanimous_correct = 0; unanimous_wrong_by_gold = Counter()
        majority_correct = 0; per_judge_correct = Counter(); definitive = 0
        for cid in ids:
            g = gold[cid]
            vs = {"mini": mini[cid][mode], "gpt54": judges["gpt54"][mode][cid], "deepseek": judges["deepseek"][mode][cid]}
            for j, v in vs.items():
                per_judge_correct[j] += (v == g)
            vals = [v for v in vs.values() if v in ("supported", "unsupported")]
            if len(vals) < 3:
                continue
            definitive += 1
            trip[(g,) + tuple(vs[j] for j in ("mini", "gpt54", "deepseek"))] += 1
            if len(set(vals)) == 1:
                unanimous += 1
                if vals[0] == g:
                    unanimous_correct += 1
                else:
                    unanimous_wrong_by_gold[g] += 1
            maj = Counter(vals).most_common(1)[0][0]
            majority_correct += (maj == g)
        report[mode] = {
            "n_definitive": definitive, "n_unanimous": unanimous,
            "p_unanimous": unanimous / definitive if definitive else None,
            "p_correct_given_unanimous": unanimous_correct / unanimous if unanimous else None,
            "unanimous_and_wrong": unanimous - unanimous_correct,
            "unanimous_and_wrong_by_gold": dict(unanimous_wrong_by_gold),
            "p_correct_majority": majority_correct / definitive if definitive else None,
            "p_correct_per_judge": {j: c / len(ids) for j, c in per_judge_correct.items()},
            "triples": {f"gold={k[0]}|mini={k[1]}|gpt54={k[2]}|deepseek={k[3]}": v for k, v in sorted(trip.items())},
        }
    OUT.write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
