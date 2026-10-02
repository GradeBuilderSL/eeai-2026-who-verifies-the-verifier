"""Rewrite operator for recorded_as_valid / cancelled_kept: the corrupted intermediate must ASSERT the stale
state in present tense (no "was published on…" / "introduced on…" cue), as a downstream paraphrase would.
Rewrites are authored by deepseek-chat from the corrupted (deletion) text; then each judge re-verifies the
false claim against the rewrite. Compares deletion-only vs rewrite corruption per judge.
"""
import argparse
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
FAMS = ("recorded_as_valid", "cancelled_kept")
REWRITE_INSTR = """You rewrite a short text as a confident downstream summary. Output ONLY JSON {"rewrite": str}.
Rules: keep every fact, name and number of the input EXCEPT: state the rule/offer/regulation as CURRENTLY in force,
in present tense, as an unconditional statement; do not mention publication, signing, announcement, adoption,
introduction, withdrawal, cancellation, annulment, or any date related to those. KEEP the exact name or title of the
rule / regulation / act / offer / programme / promotion exactly as written in the input (e.g. "the new packaging regulation",
"Municipal Ordinance 44/2026", "the 'kids fly free' promotion"). Keep the other sentence(s) as they are. 2-3 sentences, English."""


def load_cases():
    out = []
    for f in ("seed-qualifier-drop.json", "seed-qualifier-drop-deepseek.json"):
        for c in json.loads((HERE / f).read_text(encoding="utf-8")):
            if "invalid" in c or c["family"] not in FAMS or c["id"] == "cancelled_kept-ds-01":
                continue
            out.append(c)
    return out


def question(case):
    return (f"Today is {case['as_of']}. Is the claim, read as a statement about today, supported by the evidence? "
            "Preserve conditions, time intervals, effective dates, cancellations and scope. Any unsupported assertion makes it unsupported.")


def main(stage: str) -> None:
    cases = load_cases()
    if stage == "rewrite":
        common.MODEL = "deepseek-chat"
        model, _ = make_model("seed-rewrite-author-v2-20260921", max_calls=len(cases) + 2, db_path=HERE / "seed-rewrite-author-v2.sqlite",
                              provider="deepseek", output_per_call=600)
        rewrites = {}
        for c in cases:
            req = ModelRequest("seed_rewrite", REWRITE_INSTR, canonical({"text": c["corrupted"]}), 20000, 600, version="smoke-seed-rewrite.v1")
            resp = model.complete(req)
            rewrites[c["id"]] = json.loads(resp.output)["rewrite"] if resp.outcome == "completed" else None
            print(c["id"], "->", (rewrites[c["id"]] or "FAILED")[:140], flush=True)
        (HERE / "seed-rewrites-v2.json").write_text(json.dumps(rewrites, indent=2, ensure_ascii=False))
        return
    rewrites = json.loads((HERE / "seed-rewrites-v2.json").read_text(encoding="utf-8"))
    judges = {"mini": ("gpt-5.4-mini-2026-03-17", "openai"), "gpt54": ("gpt-5.4-2026-03-05", "openai"), "deepseek": ("deepseek-flash", "deepseek")}
    rows = []
    for jname, (mid, prov) in judges.items():
        common.MODEL = mid
        model, _ = make_model(f"seed-rewrite-v2-{jname}-20260921", max_calls=len(cases) + 2, db_path=HERE / f"seed-rewrite-v2-{jname}.sqlite", provider=prov)
        for c in cases:
            rw = rewrites.get(c["id"])
            v = verdict(model, question(c), c["false_claim"], rw)["verdict"] if rw else "no_rewrite"
            rows.append({"id": c["id"], "family": c["family"], "judge": jname, "rewrite_verdict": v})
            print(jname, c["id"], v, flush=True)
    summary = {}
    for jname in judges:
        for fam in FAMS:
            sub = [r for r in rows if r["judge"] == jname and r["family"] == fam]
            summary[f"{jname}/{fam}"] = {"n": len(sub), "accepts_false_on_rewrite": sum(r["rewrite_verdict"] == "supported" for r in sub)}
    (HERE / "seed-rewrite-results-v2.json").write_text(json.dumps({"summary": summary, "rows": rows}, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("stage", choices=["rewrite", "judge"])
    main(ap.parse_args().stage)
