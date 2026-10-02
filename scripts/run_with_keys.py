"""Run a harness script with API keys taken from the environment (nothing is read from files, nothing printed).

Set OPENAI_API_KEY, DEEPSEEK_API_KEY and/or TYPESAFE_API_KEY, then:
    python scripts/run_with_keys.py fr_run.py --model gpt-5.4-mini --cases fr-cases-100-v3.json
Scripts resolve data/results relative to their own folder; see scripts/README.md.
"""
import os
import runpy
import sys
from pathlib import Path

for name, plain in (("PROJECT_MEMORY_OPENAI_API_KEY", "OPENAI_API_KEY"),
                    ("PROJECT_MEMORY_DEEPSEEK_API_KEY", "DEEPSEEK_API_KEY")):
    if not os.environ.get(name) and os.environ.get(plain):
        os.environ[name] = os.environ[plain]
HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "src"))
script = HERE / sys.argv[1]
sys.argv = [str(script), *sys.argv[2:]]
runpy.run_path(str(script), run_name="__main__")
