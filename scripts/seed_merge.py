"""Merge the seed runs of several judges: per-family naive/anchored table + agreement on identical input."""
import json
from collections import Counter
import os
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
# Inputs and outputs live in one working folder (default ../work, built by prepare_work.py); override with WVV_WORK.
HERE = Path(os.environ.get("WVV_WORK", str(SCRIPTS.parent / "work")))
import sys
SUFFIX = sys.argv[1] if len(sys.argv) > 1 else ""  # e.g. "-ds" for the DeepSeek-authored seed
RUNS = {"mini": f"seed-mini{SUFFIX}-20260921.json", "gpt54": f"seed-gpt54{SUFFIX}-20260921.json", "deepseek": f"seed-deepseek{SUFFIX}-20260921.json"}


def main() -> None:
    data = {j: {r["id"]: r for r in json.loads((HERE / f).read_text())["rows"]} for j, f in RUNS.items() if (HERE / f).exists()}
    judges = list(data)
    EXCLUDE = {"cancelled_kept-ds-01"}  # few-shot leak + mis-dated (as_of precedes the withdrawal): its false claim is true
    ids = sorted(set.intersection(*(set(d) for d in data.values())) - EXCLUDE)
    fams = sorted({data[judges[0]][i]["family"] for i in ids})
    out = {"judges": judges, "n": len(ids), "by_family": {}, "agreement": {}}
    for f in fams:
        fid = [i for i in ids if data[judges[0]][i]["family"] == f]
        out["by_family"][f] = {j: {"naive_accepts_false": sum(data[j][i]["naive"] == "supported" for i in fid),
                                   "anchored_rejects": sum(data[j][i]["anchored"] == "unsupported" for i in fid),
                                   "n": len(fid)} for j in judges}
    for arm in ("naive", "anchored"):
        trip = Counter(); unanimous = unan_accept = 0
        for i in ids:
            vs = tuple(data[j][i][arm] for j in judges)
            trip[vs] += 1
            if len(set(vs)) == 1 and vs[0] in ("supported", "unsupported"):
                unanimous += 1
                unan_accept += vs[0] == "supported"
        out["agreement"][arm] = {"n_unanimous": unanimous, "unanimous_accept_false_claim": unan_accept,
                                 "per_judge_accept": {j: sum(data[j][i][arm] == "supported" for i in ids) for j in judges},
                                 "patterns": {"|".join(k): v for k, v in sorted(trip.items())}}
    (HERE / f"seed-merged{SUFFIX}.json").write_text(json.dumps(out, indent=2))
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
