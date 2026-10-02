"""T4″ — event-level extraction → journal → resolve (the architecture's own claim).

The model extracts EVENTS (adopt / replace / retract, with effective dates and optional expiry) from the
ORIGINAL; code writes them into the bitemporal store with the repo's test helpers; `resolve` computes the
value and status as of the case date. Compared with exact gold on my 20 cases. Status is never asked
from the model — that is the point being tested.
"""
import argparse
import json
import sys
import tempfile
import os
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
# Inputs and outputs live in one working folder (default ../work, built by prepare_work.py); override with WVV_WORK.
HERE = Path(os.environ.get("WVV_WORK", str(SCRIPTS.parent / "work")))
sys.path.insert(0, str(SCRIPTS))
import common  # noqa: E402
from common import make_model  # noqa: E402
from project_memory.language import ModelRequest  # noqa: E402
from project_memory.models import canonical  # noqa: E402
from project_memory.resolve import resolve  # noqa: E402
from project_memory.store import Store  # noqa: E402
from test_memory import SCOPE, add  # noqa: E402
from t4_extract import GOLD, value_match  # noqa: E402

INSTR = """Extract the EVENTS that define the fact named by "key" from the evidence. Output ONLY JSON {"events": [...]}.
Each event: {"kind": "adopt|replace|retract", "value": string or null, "effective_at": "YYYY-MM-DD",
             "expires": "YYYY-MM-DD" or null, "targets": [indices of earlier events this one replaces or retracts]}
- "adopt": a value starts to apply on effective_at (use "expires" if the text bounds it).
- "replace": a new value supersedes an earlier event's value from effective_at (targets = that earlier event).
- "retract": an earlier event is withdrawn/cancelled/annulled on effective_at (targets = that event; value null).
If a start date is not stated, use "2000-01-01". Use only the evidence. No status field, no explanation."""

# resolve-level gold: (value in force, resolve status) as of the case date
RESOLVE_GOLD = {
    "int-01": (None, "expired"), "int-02": ("2 EUR per hour", "active"), "int-03": ("19 EUR", "active"), "int-04": (None, "expired"),
    "era-01": ("39 EUR", "active"), "era-02": ("100,000 EUR", "active"), "era-03": ("10:00 to 17:00, closed on Mondays", "active"), "era-04": ("3 working days", "active"),
    "can-01": (None, "retracted"), "can-02": (None, "retracted"), "can-03": (None, "retracted"), "can-04": (None, "retracted"),
    "rec-01": (None, "unknown"), "rec-02": ("49 EUR", "active"), "rec-03": (None, "unknown"), "rec-04": (None, "unknown"),
    "cur-01": ("11,000 EUR", "active"), "cur-02": ("12.80 EUR", "active"), "cur-03": ("50 EUR", "active"), "cur-04": ("24 months", "active"),
}


def iso(d: str | None) -> str | None:
    return None if not d else f"{d}T00:00:00+00:00"


def project(events: list[dict], as_of: str) -> tuple[str, str | None, str]:
    """Write events into a fresh store and resolve as of the date. Returns (status, value, error)."""
    with tempfile.TemporaryDirectory() as tmp:
        store = Store(Path(tmp) / "m.sqlite", clock=lambda: "2000-01-01T00:00:00+00:00")
        try:
            for i, e in enumerate(events):
                kind = e["kind"]
                targets = tuple(f"e{t}" for t in (e.get("targets") or []))
                add(store, f"e{i}", kind, e.get("value"), targets, iso(e["effective_at"]), iso(e.get("expires")), SCOPE, "owner", "fact", ())
            snap = store.snapshot(SCOPE, iso(as_of), iso(as_of))
            r = resolve(snap, "fact")
            return r.status, r.value, ""
        except Exception as exc:
            return "error", None, f"{type(exc).__name__}: {str(exc)[:120]}"
        finally:
            store.close()


def main(model_name: str, provider: str, run_id: str) -> None:
    cases = {c["id"]: c for c in json.loads((HERE / "seed-qualifier-drop.json").read_text(encoding="utf-8"))}
    common.MODEL = model_name
    model, _ = make_model(run_id, max_calls=len(GOLD) + 2, db_path=HERE / f"{run_id}.sqlite", provider=provider, output_per_call=700)
    rows = []
    for cid, g in GOLD.items():
        c = cases[cid]
        req = ModelRequest("event_extraction", INSTR, canonical({"key": g["key"], "evidence": c["original"]}), 20000, 700, version="smoke-t4-events.v1")
        try:
            resp = model.complete(req); events = json.loads(resp.output)["events"]
        except Exception as exc:
            events = None; err = type(exc).__name__
        if events is None:
            status, value, err2 = "extract_error", None, err
        else:
            status, value, err2 = project(events, c["as_of"])
        gv, gs = RESOLVE_GOLD[cid]
        r = {"id": cid, "family": c["family"], "events": events, "resolved": {"status": status, "value": value}, "gold": {"value": gv, "status": gs},
             "status_ok": status == gs, "value_ok": value_match(value, gv), "error": err2}
        rows.append(r)
        print(cid, "status", status, "ok" if r["status_ok"] else "NO", "| value", value, "ok" if r["value_ok"] else "NO", "|", err2, flush=True)
    summary = {"model": model_name, "n": len(rows), "status_ok": sum(r["status_ok"] for r in rows), "value_ok": sum(r["value_ok"] for r in rows),
               "both_ok": sum(r["status_ok"] and r["value_ok"] for r in rows), "errors": sum(1 for r in rows if r["error"]),
               "by_family": {f: {"both_ok": sum(r["status_ok"] and r["value_ok"] for r in rows if r["family"] == f), "n": sum(1 for r in rows if r["family"] == f)} for f in sorted({r["family"] for r in rows})}}
    (HERE / f"{run_id}.json").write_text(json.dumps({"summary": summary, "rows": rows}, indent=2, ensure_ascii=False))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--model", default="gpt-5.4-mini-2026-03-17"); ap.add_argument("--provider", default="openai"); ap.add_argument("--run-id", default="t4-events-mini-20260921")
    a = ap.parse_args(); main(a.model, a.provider, a.run_id)
