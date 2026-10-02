# Who Verifies the Verifier? Nobody — the data does.

Materials for the talk at **EEAI 2026 — Edge AI conference, Malta, 19–21 October 2026.**
Everything on the slides is in this repository: the raw model outputs, the scripts that produced them, the
figures, the bibliography, and a one-command check that recomputes every quoted number without calling a model.

```
python verify.py        # 34 numbers, 34 reproduced from results/*.json — no API key needed
```

## The story in one minute

Edge agents cannot afford a frontier model, a long context window, or a second model call to double-check the
first. The usual answer is a verifier: a model that reads the evidence and says *supported / unsupported*. We
measured what that buys, on real versioned law with deterministic gold.

1. **The evidence path decides, not the model size.** On 100 date-anchored questions over the versioned French
   tax code (fiscal-fr-bench), gpt-5.4 answers 77 of 100 from a compressed version history, 3 of 100 from today's
   version, 91 of 100 when handed the version in force — and **99 of 100** when it is only asked for one typed
   figure per version fragment and the data model owns the dates. gpt-5.4-mini: 52 → 3 → 90 → **99**. The
   smallest model we could buy, gpt-5.4-nano, cannot even run the compress-and-answer path (69 of 100
   compressions return nothing) and still reaches **97 of 100** under the layer. *(fig. 1)*
2. **A second model is not a second opinion — when the lie is invisible.** Three independent judges (mini,
   gpt-5.4, DeepSeek) unanimously certify 2 of 97 wrong answers that are visibly stale (today's text, date
   mismatch) — and 9 of 23 wrong answers from the compressed history, where the figure is simply one version
   off. On injected restriction drops: 5 of 9 and 7 of 10. *(fig. 2)*
3. **Calibration is honesty about the input, not about the lost original.** A calibrated decision model
   (TypeSafe Jev), asked the same question as a fourth judge, signs 8 of those 9 invisible lies and all 9 wrong
   as-of answers with mean P(supported) = 0.89 — 300 verdicts, 90 seconds, $0.025. *(fig. 4)*
4. **Who verifies the verifier? The resolved value.** Comparing each answer with the journal's as-of resolution
   — no model — catches **16 of 16** wrong answers the panel certified, with 0 false alarms.
5. **Tomorrow.** Asked about a future date: where the future version is recorded, `resolve` is right 45 of 47
   times (the model reading the full history: 38); where it is not, the model invents a figure 72 of 78 times and
   the journal says "expired" 72 times. An advising edge agent must be allowed to say *I don't know*. *(fig. 3)*

The mechanism is old and small: a bitemporal event journal (valid time + transaction time, supersession chain)
and a deterministic as-of resolver. The model's only job is typed extraction — one figure, one date, per
fragment. The novelty, if any, is the measurement: *where* verification by agreement fails, and that the data
model catches exactly those cases.

## Numbers to quote (cheat sheet)

| | gpt-5.4 | gpt-5.4-mini | gpt-5.4-nano |
| --- | --- | --- | --- |
| A — compress the history, then answer | 77 | 52 (repeats: 66, 60) | 12 (69 blank) |
| B — today's version (static RAG) | 3 | 3 | 3 |
| C — version in force (oracle) | 91 | 90 | 91 |
| D — one typed figure per version, data own the dates | **99** | **99** (99, 99) | **97** |

Three-judge unanimous certification of WRONG answers: A 9/23 (39 %; 9 of the 19 the judges saw) · B 2/97 (2 %) ·
injected drops 5/9, 7/10 · natural summarizer errors 0/28. Jev: A 10/19, C 9/9 at P̄ 0.89, rejects 1 of 9.
Resolved value: 16/16 caught, 0 false alarms. Tomorrow: 45/47 vs 38; 72 invented vs 72 declined.
Whole study ≈ $35 of API calls. Full table with file names: [`results/README.md`](results/README.md).

## What is here

| Folder | Contents |
| --- | --- |
| [`verify.py`](verify.py) | recomputes every number above from the raw files; exits non-zero on any mismatch |
| [`results/`](results/) | raw JSON of every run quoted in the talk — each row keeps the full model output |
| [`data/`](data/) | the 100 benchmark cases with their evidence texts (CC BY 4.0, from fiscal-fr-bench) and the injected seeds |
| [`scripts/`](scripts/) | the harness exactly as run (prompts inline), plus the offline 3-minute stage demo |
| [`src/project_memory/`](src/project_memory/) | the journal, the as-of resolver and the model adapter the scripts import (subset of the project-memory core) |
| [`figures/`](figures/) | the four figures as PNG / SVG / PDF and `make_figures.py` to redraw them |
| [`docs/`](docs/) | the results reports (22 Sep, 2 Oct) and the 557-entry bibliography with its honest header |
| [`slides/`](slides/) | the slides as PDF, added after the talk |

## Reproduce

```
pip install -r requirements.txt
python scripts/prepare_work.py                                   # work/ = copies of data/ + results/
python scripts/run_with_keys.py demo_three_ways.py               # offline: one question, three ways
export OPENAI_API_KEY=...                                        # to rerun a condition (cents each)
python scripts/run_with_keys.py fr_run.py --model gpt-5.4-mini --run-id rerun --cases fr-cases-100-v3.json
```

Rerun costs: a 100-question condition on gpt-5.4-mini is a few cents; the 300-verdict Jev run $0.025.
Commands for every script: [`scripts/README.md`](scripts/README.md).

## What we do not claim

No new algorithm: bitemporal journals are the database world's, as-of resolution is SQL:2011, supersession and
provenance are standard. One run per condition unless stated (mini repeated three times). 100 of the
benchmark's 209 hard questions, one domain, French legal text with an English verifier prompt, compression by
the same model family as the answerer. The layer is implemented and tested (1,099 tests) and integrated behind
feature flags in a product; it is not enabled for customers.

## Related work we stand next to

Zep / Graphiti and MemStrata (agent memory with time), TOKI and Engram, FiscalQA / fiscal-fr-bench (versioned
legal retrieval), FAITH (faithfulness and time), StateAuditor and the Selective-QA line (fail-closed answers),
LLM-Modulo and Simplex (model proposes, verifier disposes), the correlated-judges literature. The bibliography
([`docs/bibliography/`](docs/bibliography/)) has 557 entries, 537 checked against the primary source.

## About the authors

The study comes out of [**Laspi.Pro**](https://laspi.pro) — an AI content assistant for small businesses: the
owner talks for two minutes, the system writes the week's posts, pictures and short videos. Laspi has to remember
what a business said *and when it stopped being true* — prices, opening hours, offers that expire — which is
where this question came from. The journal measured here is Laspi's memory layer in the making.

## Cite

The citation metadata is in [`CITATION.cff`](CITATION.cff); a versioned DOI is issued through Zenodo for each
GitHub release. The benchmark must be cited separately — see [`data/README.md`](data/README.md).

## Licenses

Code (`scripts/`, `src/`, `verify.py`, `figures/make_figures.py`): **Apache License 2.0** — [`LICENSE`](LICENSE).
Talk materials, figures, reports, bibliography and our seed data: **CC BY 4.0** — [`LICENSE-CC-BY-4.0`](LICENSE-CC-BY-4.0).
`data/fr-cases-100-v3.json` carries fiscal-fr-bench's CC BY 4.0 terms and the Licence Ouverte / Etalab 2.0
attribution of the Légifrance texts.
