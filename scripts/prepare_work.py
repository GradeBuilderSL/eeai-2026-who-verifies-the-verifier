"""Build the working folder the harness scripts read from and write to: work/ = data/ + results/ (copies).

    python scripts/prepare_work.py      # then e.g.  python scripts/run_with_keys.py demo_three_ways.py
Set WVV_WORK to use another folder. Nothing in data/ or results/ is modified by the scripts.
"""
import os
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORK = Path(os.environ.get("WVV_WORK", str(ROOT / "work")))
WORK.mkdir(parents=True, exist_ok=True)
n = 0
for folder in ("data", "results"):
    for f in (ROOT / folder).iterdir():
        if f.suffix == ".json":
            shutil.copy2(f, WORK / f.name); n += 1
print(f"{n} files copied to {WORK}")
