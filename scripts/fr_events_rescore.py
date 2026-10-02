"""Rescore stored D v4 events with three harness fixes, no model calls:
 1. projection clock: events were stamped recorded_at=2000-01-01, hiding them for as-of dates before 2000 (bitemporal filter);
 2. source versions with inverted ranges (expires <= effective_at) raised in the store — expiry dropped for those;
 3. old-franc thousands with a dot ("22.100 F") were parsed as 22.1 — normalised before nugget scoring."""
import json
import re
import sys
import tempfile
import os
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
# Inputs and outputs live in one working folder (default ../work, built by prepare_work.py); override with WVV_WORK.
HERE = Path(os.environ.get("WVV_WORK", str(SCRIPTS.parent / "work")))
sys.path.insert(0, str(SCRIPTS))
from fr_run import strict  # noqa: E402
from project_memory.resolve import resolve  # noqa: E402
from project_memory.store import Store  # noqa: E402
from test_memory import SCOPE, add  # noqa: E402


def iso(d):
    return None if not d else f"{d}T00:00:00+00:00"


def project_fixed(events, as_of):
    with tempfile.TemporaryDirectory() as tmp:
        store = Store(Path(tmp) / "m.sqlite", clock=lambda: "1900-01-01T00:00:00+00:00")
        try:
            for i, e in enumerate(events):
                exp = e.get("expires")
                if exp and e["effective_at"] and exp <= e["effective_at"]:
                    exp = None
                add(store, f"e{i}", e["kind"], e.get("value"), tuple(f"e{t}" for t in (e.get("targets") or [])), iso(e["effective_at"]), iso(exp), SCOPE, "owner", "fact", ())
            r = resolve(store.snapshot(SCOPE, iso(as_of), iso(as_of)), "fact")
            return r.status, r.value, ""
        except Exception as exc:
            return "error", None, f"{type(exc).__name__}: {str(exc)[:80]}"
        finally:
            store.close()


def fix_thousands(v):
    return re.sub(r"(?<=\d)\.(?=\d{3}\b)", " ", v) if v else v


def main(run_file, cases_file="fr-cases-v3.json"):
    cases = {c["qid"]: c for c in json.loads((HERE / cases_file).read_text(encoding="utf-8"))}
    d = json.loads((HERE / run_file).read_text(encoding="utf-8"))
    ok = 0; rows = []
    for r in d["rows"]:
        c = cases[r["qid"]]
        status, value, err = project_fixed(r["events"], c["date_anchor"]) if r["events"] else ("no_events", None, "")
        answer = f"Article {c['article_num']} : {fix_thousands(value)}" if value else ""
        correct = strict(c["nuggets"], answer) if answer else False
        ok += correct; rows.append({"qid": r["qid"], "status": status, "value": value, "correct": correct, "error": err})
    from collections import Counter
    print(run_file, "RESCORED accuracy", f"{ok}/{len(rows)}", "statuses", dict(Counter(x["status"] for x in rows)))
    print("  still wrong:", [(x["qid"][6:24], x["status"], (x["value"] or "")[:14]) for x in rows if not x["correct"]])
    (HERE / run_file.replace(".json", ".rescored.json")).write_text(json.dumps({"accuracy": f"{ok}/{len(rows)}", "rows": rows}, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    for f in sys.argv[1:]:
        main(f)
