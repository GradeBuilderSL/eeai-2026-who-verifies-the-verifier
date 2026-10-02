"""T4' — extraction risk for Resolved Generation: can a model build the typed record from the ORIGINAL?

For each of my 20 seed originals (gold known exactly because I wrote them), the model reads the original
and the as-of date and returns JSON {value_in_force, status, valid_from, valid_to}. Scored against gold
on (value_in_force, status) exactly and on dates when gold has them. This is ChatGPT's abandon criterion #1
("typed-state extraction is the main error source") tested directly — the real T4, not the tautology.
"""
import argparse
import json
import sys
import os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import common  # noqa: E402
from common import make_model  # noqa: E402
from project_memory.language import ModelRequest  # noqa: E402
from project_memory.models import canonical  # noqa: E402

SCRIPTS = Path(__file__).resolve().parent
# Inputs and outputs live in one working folder (default ../work, built by prepare_work.py); override with WVV_WORK.
HERE = Path(os.environ.get("WVV_WORK", str(SCRIPTS.parent / "work")))
INSTR = """Extract the state of the fact named by "key" on the date "as_of" from the evidence. Output ONLY JSON:
{"value_in_force": string or null, "status": "active|expired|not_yet_effective|superseded|cancelled|unknown",
 "valid_from": "YYYY-MM-DD" or null, "valid_to": "YYYY-MM-DD" or null}
"value_in_force" = the value that actually applies on as_of (short, e.g. "39 EUR", "free", "none"); null if nothing applies.
Use only the evidence. Dates in ISO format. No explanation."""

# Gold for my 20 self-authored cases (value that applies on as_of; status on as_of; interval of the ORIGINAL rule)
GOLD = {
    "int-01": {"key": "online discount on city bikes", "value_in_force": "none", "status": "expired", "valid_from": None, "valid_to": "2026-08-31"},
    "int-02": {"key": "parking tariff on Harbour Street for permit holders", "value_in_force": "2 EUR per hour", "status": "expired", "valid_from": "2026-06-01", "valid_to": "2026-09-30"},
    "int-03": {"key": "monthly price of the Pro plan for a subscriber who joined in April 2026", "value_in_force": "19 EUR", "status": "expired", "valid_from": None, "valid_to": None},
    "int-04": {"key": "free repair warranty for a machine bought in January 2025", "value_in_force": "none", "status": "expired", "valid_from": "2025-01-01", "valid_to": "2027-01-31"},
    "era-01": {"key": "monthly fee of the Basic tariff", "value_in_force": "39 EUR", "status": "active", "valid_from": "2026-09-01", "valid_to": None},
    "era-02": {"key": "VAT registration threshold", "value_in_force": "100,000 EUR", "status": "active", "valid_from": "2026-07-01", "valid_to": None},
    "era-03": {"key": "museum opening hours", "value_in_force": "10:00 to 17:00, closed on Mondays", "status": "active", "valid_from": "2026-10-01", "valid_to": None},
    "era-04": {"key": "standard delivery time", "value_in_force": "3 working days", "status": "active", "valid_from": "2026-08-01", "valid_to": None},
    "can-01": {"key": "mandatory three-days-in-office rule", "value_in_force": "none", "status": "cancelled", "valid_from": "2026-03-01", "valid_to": "2026-06-15"},
    "can-02": {"key": "kids fly free promotion", "value_in_force": "none", "status": "cancelled", "valid_from": "2026-05-02", "valid_to": "2026-06-09"},
    "can-03": {"key": "short-term rental ban in the old town", "value_in_force": "none", "status": "cancelled", "valid_from": "2026-02-10", "valid_to": "2026-07-30"},
    "can-04": {"key": "heat-pump subsidy for owner-occupied homes (new applications)", "value_in_force": "none", "status": "cancelled", "valid_from": "2026-04-01", "valid_to": "2026-10-31"},
    "rec-01": {"key": "new packaging regulation", "value_in_force": "none", "status": "not_yet_effective", "valid_from": "2026-04-01", "valid_to": None},
    "rec-02": {"key": "Premium tariff price for invoices", "value_in_force": "49 EUR", "status": "not_yet_effective", "valid_from": "2026-10-01", "valid_to": None},
    "rec-03": {"key": "updated travel policy", "value_in_force": "none", "status": "not_yet_effective", "valid_from": "2026-07-01", "valid_to": None},
    "rec-04": {"key": "reduced 7% VAT rate for restaurant meals", "value_in_force": "none", "status": "not_yet_effective", "valid_from": "2027-01-01", "valid_to": None},
    "cur-01": {"key": "tax-free allowance", "value_in_force": "11,000 EUR", "status": "active", "valid_from": None, "valid_to": "2026-12-31"},
    "cur-02": {"key": "minimum hourly wage", "value_in_force": "12.80 EUR", "status": "active", "valid_from": None, "valid_to": "2026-12-31"},
    "cur-03": {"key": "free delivery threshold", "value_in_force": "50 EUR", "status": "active", "valid_from": None, "valid_to": "2026-11-30"},
    "cur-04": {"key": "retention period of customer support logs", "value_in_force": "24 months", "status": "active", "valid_from": "2026-05-01", "valid_to": "2027-01-31"},
}


def norm_value(v):
    if v is None:
        return "none"
    s = str(v).lower().replace("€", "eur").replace(",", "").replace("per month", "").replace("/month", "").strip()
    s = s.replace("euro", "eur").replace("eur ", "eur").replace(" eur", "eur")
    return " ".join(s.split())


def value_match(pred, gold):
    p, g = norm_value(pred), norm_value(gold)
    if g == "none":
        return p in ("none", "null", "", "not applicable", "n/a", "no discount", "not covered", "not in force", "not available")
    gnum = "".join(ch for ch in g if ch.isdigit())
    pnum = "".join(ch for ch in p if ch.isdigit())
    return p == g or (gnum and gnum == pnum) or (g in p)


def main(model_name: str, provider: str, run_id: str) -> None:
    cases = {c["id"]: c for c in json.loads((HERE / "seed-qualifier-drop.json").read_text(encoding="utf-8"))}
    common.MODEL = model_name
    model, _ = make_model(run_id, max_calls=len(GOLD) + 2, db_path=HERE / f"{run_id}.sqlite", provider=provider, output_per_call=300)
    rows = []
    for cid, g in GOLD.items():
        c = cases[cid]
        req = ModelRequest("typed_extraction", INSTR, canonical({"key": g["key"], "as_of": c["as_of"], "evidence": c["original"]}), 20000, 300, version="smoke-t4-extract.v1")
        try:
            resp = model.complete(req); out = json.loads(resp.output)
        except Exception as exc:
            out = {"error": type(exc).__name__}
        r = {"id": cid, "family": c["family"], "pred": out, "gold": g,
             "value_ok": value_match(out.get("value_in_force"), g["value_in_force"]) if "error" not in out else False,
             "status_ok": out.get("status") == g["status"],
             "from_ok": (out.get("valid_from") == g["valid_from"]) if g["valid_from"] else None,
             "to_ok": (out.get("valid_to") == g["valid_to"]) if g["valid_to"] else None}
        rows.append(r)
        print(cid, "value", r["value_ok"], "status", r["status_ok"], "from", r["from_ok"], "to", r["to_ok"], "|", out, flush=True)
    n = len(rows)
    summary = {"model": model_name, "n": n, "value_ok": sum(r["value_ok"] for r in rows), "status_ok": sum(r["status_ok"] for r in rows),
               "both_ok": sum(r["value_ok"] and r["status_ok"] for r in rows),
               "from_ok": f"{sum(1 for r in rows if r['from_ok'])}/{sum(1 for r in rows if r['from_ok'] is not None)}",
               "to_ok": f"{sum(1 for r in rows if r['to_ok'])}/{sum(1 for r in rows if r['to_ok'] is not None)}",
               "by_family": {f: {"both_ok": sum(r["value_ok"] and r["status_ok"] for r in rows if r["family"] == f), "n": sum(1 for r in rows if r["family"] == f)} for f in sorted({r["family"] for r in rows})}}
    (HERE / f"{run_id}.json").write_text(json.dumps({"summary": summary, "rows": rows}, indent=2, ensure_ascii=False))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--model", default="gpt-5.4-mini-2026-03-17"); ap.add_argument("--provider", default="openai"); ap.add_argument("--run-id", default="t4-extract-mini-20260921")
    a = ap.parse_args(); main(a.model, a.provider, a.run_id)
