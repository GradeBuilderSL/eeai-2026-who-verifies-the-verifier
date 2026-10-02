"""recorded_as_valid, object-level claims: the claim is the rule's own assertion (what the rewrite says), not the
meta-statement "X is in force". deepseek-chat derives one unqualified present-tense claim from each rewrite-v2
text; three judges verify it against the rewrite (naive) and against the original + as-of (anchored)."""
import json
import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import common  # noqa: E402
from common import make_model, verdict  # noqa: E402
from project_memory.language import ModelRequest  # noqa: E402
from project_memory.models import canonical  # noqa: E402

SCRIPTS = Path(__file__).resolve().parent
# Inputs and outputs live in one working folder (default ../work, built by prepare_work.py); override with WVV_WORK.
HERE = Path(os.environ.get("WVV_WORK", str(SCRIPTS.parent / "work")))
CLAIM_INSTR = """From the text, write ONE short present-tense sentence stating the main rule/obligation/right it asserts, with no
dates, no mention of publication or entry into force, no hedging. Output ONLY JSON {"claim": string}."""


def question(case):
    return (f"Today is {case['as_of']}. Is the claim, read as a statement about today, supported by the evidence? "
            "Preserve conditions, time intervals, effective dates, cancellations and scope. Any unsupported assertion makes it unsupported.")


def main():
    cases = []
    for f in ("seed-qualifier-drop.json", "seed-qualifier-drop-deepseek.json"):
        cases += [c for c in json.loads((HERE / f).read_text(encoding="utf-8")) if "invalid" not in c and c["family"] == "recorded_as_valid"]
    rewrites = json.loads((HERE / "seed-rewrites-v2.json").read_text(encoding="utf-8"))
    common.MODEL = "deepseek-chat"
    author, _ = make_model("rec-objclaim-author-20260921", max_calls=len(cases) + 2, db_path=HERE / "rec-objclaim-author.sqlite", provider="deepseek", output_per_call=200)
    claims = {}
    for c in cases:
        req = ModelRequest("objclaim", CLAIM_INSTR, canonical({"text": rewrites[c["id"]]}), 20000, 200, version="smoke-objclaim.v1")
        resp = author.complete(req)
        claims[c["id"]] = json.loads(resp.output)["claim"] if resp.outcome == "completed" else None
        print(c["id"], "CLAIM:", claims[c["id"]], flush=True)
    judges = {"mini": ("gpt-5.4-mini-2026-03-17", "openai"), "gpt54": ("gpt-5.4-2026-03-05", "openai"), "deepseek": ("deepseek-flash", "deepseek")}
    rows = []
    for jname, (mid, prov) in judges.items():
        common.MODEL = mid
        model, _ = make_model(f"rec-objclaim-{jname}-20260921", max_calls=len(cases) * 2 + 2, db_path=HERE / f"rec-objclaim-{jname}.sqlite", provider=prov)
        for c in cases:
            cl = claims.get(c["id"])
            if not cl:
                continue
            naive = verdict(model, question(c), cl, rewrites[c["id"]])["verdict"]
            anch = verdict(model, question(c), cl, c["original"])["verdict"]
            rows.append({"id": c["id"], "judge": jname, "claim": cl, "naive": naive, "anchored": anch})
            print(jname, c["id"], "naive", naive, "anchored", anch, flush=True)
    summary = {j: {"n": sum(1 for r in rows if r["judge"] == j), "naive_accepts": sum(1 for r in rows if r["judge"] == j and r["naive"] == "supported"),
                   "anchored_rejects": sum(1 for r in rows if r["judge"] == j and r["anchored"] == "unsupported")} for j in judges}
    (HERE / "rec-objclaims-results.json").write_text(json.dumps({"claims": claims, "summary": summary, "rows": rows}, indent=1, ensure_ascii=False))
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
