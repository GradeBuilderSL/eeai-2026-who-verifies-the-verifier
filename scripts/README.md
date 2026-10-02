# Scripts — the harness, as run

Experiment tooling, not library code: each file is one measurement, written the day it ran (21–22 September and
2 October 2026). Prompts are inline: the verifier prompt is `src/project_memory/verification_experiment.py`
(`evidence_request`), the judges' prompt is in `fr_judges.py`, the event-extraction prompt in `fr_events_v4.py`,
the Jev question in `jev_judge.py`.

```
pip install -r requirements.txt
export OPENAI_API_KEY=...  DEEPSEEK_API_KEY=...  TYPESAFE_API_KEY=...     # only what you rerun
python scripts/prepare_work.py                                            # work/ = copies of data/ + results/
python scripts/run_with_keys.py demo_three_ways.py                        # no network: the stage demo from cached files
python scripts/run_with_keys.py fr_run.py --model gpt-5.4-mini --run-id fr-mini-100v3-rerun --cases fr-cases-100-v3.json
python scripts/run_with_keys.py fr_events_v4.py --model gpt-5.4-mini --run-id fr-events-v4-mini-rerun --cases fr-cases-100-v3.json
python scripts/run_with_keys.py fr_events_rescore.py fr-events-v4-mini-rerun.json fr-cases-100-v3.json
python scripts/run_with_keys.py fr_judges.py                              # three judges over the stored gpt-5.4 answers
python scripts/run_with_keys.py jev_judge.py judge --run-file fr-gpt54-100v3-20260921.json
python scripts/run_with_keys.py jev_judge.py report --run-file fr-gpt54-100v3-20260921.json
python scripts/run_with_keys.py fr_predict.py --model gpt-5.4 --run-id fr-predict-gpt54-rerun
```

Scripts read and write `work/` (override with `WVV_WORK`); `data/` and `results/` are never modified.

| Script | What it measures |
| --- | --- |
| `fr_build.py` | cuts the 100 cases from a local clone of fiscal-fr-bench (`FISCAL_FR_BENCH_DIR`) |
| `fr_run.py` | conditions A (compress, then answer) / B (today's version) / C (version in force), with the answerer as its own verifier |
| `fr_events_v4.py`, `fr_events_rescore.py` | condition D: one typed figure per version fragment → journal → `resolve` on the date |
| `fr_judges.py` | three independent judges over stored answers; `jev_judge.py` — the calibrated decision model as a fourth |
| `fr_predict.py` | tomorrow: answer about d2 from the history known at d1 (recorded vs invented future) |
| `demo_three_ways.py` | the stage demo: one question, three ways, from cached files |
| `seed_build.py`, `seed_author.py`, `seed_rewrite.py`, `seed_rec_objclaims.py`, `seed_tests.py`, `seed_merge.py` | the injected restriction-drop seeds and the three-judge runs on them |
| `t2b_three_judges.py`, `t3_placebo_length.py` | natural summarizer errors (AggreFact): agreement is informative; length explains the yes-bias. These two need the earlier H1 materials (`PM_RUNS`), which are not in this release; their result files are |
| `t4_extract.py`, `t4_events.py` | ask the model for a status label vs. ask for events and compute the status |
| `common.py`, `qualifiers.py`, `test_memory.py` | shared wiring; qualifier-span finder; two helpers from the core's test module |

`src/project_memory/` is the subset of the project-memory core the harness imports (12 modules of version
0.1.10): the event journal (`store.py`), the as-of resolver with the supersession chain (`resolve.py`), the model
request contract and the OpenAI-compatible adapter with per-run budgets, and the verifier prompt. It is the
mechanism being measured, included so that every number can be rerun; it is not a packaged library.
