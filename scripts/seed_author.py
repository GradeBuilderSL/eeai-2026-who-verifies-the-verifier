"""Independent authoring of qualifier-drop cases by a DIFFERENT model (DeepSeek), from the family spec.

The coordinator writes no scenario. The model marks the critical restriction(s) with [[...]] and one
decoy restriction with ((...)); code turns markers into segments, so corruption (delete critical
spans) and gold stay by construction. Partial independence only (the model follows our spec), as
in H3 — but the scenario-level authoring bias is no longer ours.
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import common  # noqa: E402
from common import make_model  # noqa: E402
from project_memory.language import ModelRequest  # noqa: E402
from project_memory.models import canonical  # noqa: E402

OUT = Path(__file__).parent / "seed-qualifier-drop-deepseek.json"
AUTHOR_MODEL = "deepseek-chat"
FAMILIES = {
    "interval_dropped": "The fact holds only inside a time interval (until/from/between/for N months). The critical restriction is that interval. Removing it makes the fact look unconditional.",
    "eras_merged": "The fact changed value at some date. Write it so the CURRENT value is inside the critical span and the OLD value stays in PRESENT tense when the span is removed, e.g. 'The monthly fee is 29 EUR[[; since 1 September 2026 it is 39 EUR]].' Removing the span must leave the stale value reading as current.",
    "cancelled_kept": "A rule/offer/programme was introduced and later withdrawn/cancelled/annulled. The critical span is the sentence or clause stating the withdrawal. Removing it makes the cancelled rule look in force.",
    "recorded_as_valid": "Something was published/signed/announced on one date and takes effect on a LATER date. The critical span is the entry-into-force clause. Removing it makes the publication date look like the effective date.",
    "cursor_ignored": "A future value is stated together with the current one, e.g. 'The threshold is set at 30 EUR[[ from 1 December 2026; until then it is 50 EUR]].' The critical span carries the as-of cursor and the current value; removing it makes the future value read as current.",
    "layered": "ONE fact carries TWO independent restrictions of different kinds (a time interval AND a scope/eligibility condition; or a scope AND a quantity threshold). Mark BOTH as critical [[...]] [[...]]. The false_claim must drop BOTH restrictions (fully unqualified statement of the fact). On as_of, EACH restriction ALONE must already make the false claim false (e.g. as_of is after the interval AND the claim covers people outside the scope), so that deleting only one span still leaves a contradiction in the text. Put the decoy ((...)) in another sentence.",
}
INSTRUCTIONS = """You write test cases for a verifier benchmark about RESTRICTIONS that get lost between pipeline stages.
Output ONLY JSON: {"cases": [...]}, exactly N cases. Each case:
{"id": str, "domain": str, "as_of": "YYYY-MM-DD", "original": str, "false_claim": str, "true_claim": str, "why_false": str}

Definitions:
- "original": 2-3 realistic English sentences (invented names, plausible numbers) stating a fact WITH its restriction(s).
  Mark each CRITICAL restriction with [[ ]] and exactly ONE unrelated DECOY restriction with (( )).
  After deleting the marked text (markers included) the remaining sentence MUST still be grammatical and MUST read as a
  confident present-tense statement of the fact WITHOUT the restriction. Put the restriction at the END of its clause.
- "false_claim": one date-free sentence stating the fact as if the critical restriction did not exist. It must be FALSE on
  the date "as_of" precisely because of the critical restriction, and it must NOT rely on the decoy.
- "true_claim": one sentence true on "as_of" given the full original.
- "why_false": one line explaining which restriction makes the false claim false on as_of.
- Never write the as_of date inside a claim.

Family rule for this batch: {family_rule}

Worked example (family interval_dropped): original = "Nordvik Bikes offers a 20% discount on all city bikes ((for customers
who order online)) [[until 31 August 2026]]. The discount is applied automatically at checkout." as_of = "2026-09-15";
false_claim = "Nordvik Bikes offers a 20% discount on all city bikes for customers who order online."; true_claim =
"Nordvik Bikes' 20% online discount on city bikes ended on 31 August 2026."
Worked example (family eras_merged): original = "The monthly fee for the Basic tariff is 29 EUR[[; since 1 September 2026
it is 39 EUR]]. Existing customers were notified ((by e-mail on 20 August 2026))." as_of = "2026-09-21"; false_claim =
"The monthly fee for the Basic tariff is 29 EUR."; true_claim = "The monthly fee for the Basic tariff is 39 EUR."
Worked example (family cancelled_kept): original = "On 1 March 2026 the company introduced a mandatory three-days-in-office
rule ((for all staff)). [[The rule was withdrawn on 15 June 2026 after the works council objected.]] Team leads may still
agree local arrangements." as_of = "2026-09-01"; false_claim = "A mandatory three-days-in-office rule is in force for all
staff."; true_claim = "The mandatory three-days-in-office rule was withdrawn on 15 June 2026."
Worked example (family recorded_as_valid): original = "The new packaging regulation was published in the official journal
on 12 March 2026 [[and enters into force on 1 April 2026]]. It applies to ((producers placing more than 10 tonnes on the
market per year))." as_of = "2026-03-20"; false_claim = "The new packaging regulation is in force."; true_claim = "The new
packaging regulation enters into force on 1 April 2026."
Worked example (family cursor_ignored): original = "The tax-free allowance is set at 12,000 EUR [[from 1 January 2027;
until then it remains 11,000 EUR]]. The allowance is granted ((only to residents))." as_of = "2026-06-15"; false_claim =
"The tax-free allowance is 12,000 EUR."; true_claim = "The tax-free allowance is 11,000 EUR."
Worked example (family layered): original = "Harbour Ferries carries bicycles free of charge [[on weekdays]] [[for holders of
a monthly pass]]. Bicycles are ((not)) allowed on the 07:30 sailing. The company was founded in 1998." as_of = "2026-09-19"
(a Saturday); false_claim = "Harbour Ferries carries bicycles free of charge."; true_claim = "On Saturdays, or without a
monthly pass, Harbour Ferries charges for bicycles." (removing only ONE of the two critical spans must still contradict the
false claim).

Use different domains and names from the examples. Do not explain outside the JSON."""


def to_segments(marked: str) -> list[dict]:
    segs, pos = [], 0
    for m in re.finditer(r"\[\[(.+?)\]\]|\(\((.+?)\)\)", marked):
        if m.start() > pos:
            segs.append({"text": marked[pos:m.start()], "kind": None, "critical": False})
        if m.group(1) is not None:
            segs.append({"text": m.group(1), "kind": "critical", "critical": True})
        else:
            segs.append({"text": m.group(2), "kind": "decoy", "critical": False})
        pos = m.end()
    if pos < len(marked):
        segs.append({"text": marked[pos:], "kind": None, "critical": False})
    return segs


def clean(text: str) -> str:
    return re.sub(r"\s+([.,;])", r"\1", re.sub(r"\s{2,}", " ", text)).strip()


def author(model, family: str, n: int) -> list[dict]:
    req = ModelRequest("seed_authoring", INSTRUCTIONS.replace("{family_rule}", FAMILIES[family]).replace("N cases", f"{n} cases"),
                       canonical({"family": family, "n": n}), 20000, 5000, version="smoke-seed-author.v1")
    resp = model.complete(req)
    if resp.outcome != "completed":
        raise RuntimeError(f"{family}: {resp.outcome}")
    data = json.loads(resp.output)
    out = []
    for i, c in enumerate(data["cases"][:n]):
        segs = to_segments(c["original"])
        crit = [s for s in segs if s["critical"]]
        expected = 2 if family == "layered" else 1
        if len(crit) != expected or not any(s["kind"] == "decoy" for s in segs):
            out.append({"id": f"{family}-ds-{i+1:02d}", "family": family, "invalid": f"critical={len(crit)} decoy={any(s['kind']=='decoy' for s in segs)}", "raw": c})
            continue
        original = clean("".join(s["text"] for s in segs))
        corrupted = clean("".join(s["text"] for s in segs if not s["critical"]))
        spans = [dict(index=k, kind=s["kind"], text=s["text"], critical=s["critical"]) for k, s in enumerate(segs) if s["kind"]]
        out.append({"id": f"{family}-ds-{i+1:02d}", "family": family, "domain": c.get("domain", ""), "as_of": c["as_of"],
                    "false_claim": c["false_claim"].strip(), "true_claim": c["true_claim"].strip(),
                    "original": original, "corrupted": corrupted, "spans": spans, "segments": segs, "author": AUTHOR_MODEL, "why_false": c.get("why_false", ""),
                    "gold": {"false_claim_vs_original": "unsupported", "true_claim_vs_original": "supported",
                             "false_claim_vs_corrupted_by_construction": "appears_supported"}})
    return out


def main(n_per_family: int, run_id: str = "seed-author-deepseek-chat-20260921") -> None:
    common.MODEL = AUTHOR_MODEL
    model, _ = make_model(run_id, max_calls=len(FAMILIES) * 2 + 2,
                          db_path=Path(__file__).parent / f"{run_id}.sqlite", provider="deepseek", output_per_call=5000)
    cases = []
    for fam in FAMILIES:
        try:
            got = author(model, fam, n_per_family)
        except Exception as exc:
            print(fam, "FAILED", type(exc).__name__, str(exc)[:200]); continue
        cases.extend(got)
        print(fam, "ok", sum(1 for c in got if "invalid" not in c), "valid of", len(got), flush=True)
    OUT.write_text(json.dumps(cases, indent=2, ensure_ascii=False))
    valid = [c for c in cases if "invalid" not in c]
    print(len(valid), "valid cases ->", OUT.name)
    for c in valid[:3]:
        print(c["id"], "|", c["original"], "|| FALSE:", c["false_claim"])


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--n", type=int, default=4)
    ap.add_argument("--family", default=None); ap.add_argument("--out", default=None); ap.add_argument("--run-id", default="seed-author-deepseek-chat-20260921")
    a = ap.parse_args()
    if a.family:
        FAMILIES = {a.family: FAMILIES[a.family]}
    if a.out:
        OUT = Path(a.out)
    main(a.n, a.run_id)
