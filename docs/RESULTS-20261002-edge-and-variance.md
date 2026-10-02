# Results addendum — edge-class model and run-to-run variance (2 October 2026)

Companion to `RESULTS-20260922.md` and `TALK-PACK-20260922.md`. Same harness, same 100-question
set (`smoke-tests-20260921/fr-cases-100-v3.json`, fiscal-fr-bench "killer" R3 questions, deterministic
nugget scoring), same prompts and caps. Run on the owner's Windows laptop with a fresh interpreter
(`memory-workspace/pm-venv`); keys injected by `smoke-tests-20260921/run_with_keys.py`.
Condition D numbers are after `fr_events_rescore.py`, exactly like the published 198/200.
Total cost of this addendum ≈ $1 (nano) + ≈ $2 (mini repeats).

## 1. The smallest purchasable model (gpt-5.4-nano)

| Condition | gpt-5.4-nano | gpt-5.4-mini (21.09) | gpt-5.4 (21.09) |
| --- | --- | --- | --- |
| A — compressed history, then answer | **12/100** — 69 of 100 compressions returned nothing (no completed JSON within the 700-token cap); of the 31 that ran, 12 right; as its own verifier it accepted 18 of its 19 wrong answers | 52 (repeat: 66) | 77 |
| B — today's version (static RAG) | 3/100 | 3 | 3 |
| C — version in force on the date (benchmark oracle) | **91/100** | 90 | 91 |
| D — one typed figure per version + data-owned time, `resolve` | **97/100** | 99 | 99 |

Files: `fr-nano-100v3-20261002.json` (A/B/C), `fr-events-v4-nano-100v3-20261002.json` +
`.rescored.json` (D; raw before rescore 67/100 with 19 `unknown`, identical shape to mini/gpt-5.4
raw 68/100 — the same harness fixes apply).

The three D misses: `R3-WS-50-0-1996-05-12` (nano extracted 120 000 F; the fragment's asked value is
100 000 F), `R3-WS-1586nonies-2014-01-01` (nano extracted the 2-million-euro value-added threshold
instead of the asked 135 380 € amount) and `R3-WS-1605bis-2021-01-01` (shared by every model; the
inverted validity range documented in RESULTS-20260922 §4). **Both nano-specific misses are
"which figure does the question ask about" errors inside one fragment; none is a date or version
error.** That is the division of labour the architecture claims: the model's remaining job is typed
extraction, and that is the only place the smallest model still slips.

Reading for the talk (precision rules from TALK-PACK §0 still apply — never "cheaper", never
"small beats large"): *with the layer, model size stops mattering — 97 ≈ 99 ≈ 99*; without the
layer the smallest model cannot even run the compress-and-answer pipeline. Condition C shows the
same: handed the right version, nano reads it as well as gpt-5.4 (91 = 91). What the layer removes
is the part where size (and luck) matters: compressing a history and reasoning about dates.

## 2. Run-to-run variance (gpt-5.4-mini, three runs each)

| Condition | run 1 (21.09) | run 2 (02.10) | run 3 (02.10) |
| --- | --- | --- | --- |
| D (rescored) | 99 | 99 | 99 — the same single miss (1605 bis) every time |
| C | 90 | 90 | 91 |
| B | 3 | 3 | 3 |
| A | 52 | 66 | 60 |

D is deterministic given the extracted events; the only stochastic step (one typed figure per
fragment) reproduced exactly. A moved by up to 14 cases between runs (52 / 66 / 60; the verifier accepted 36/48, 21/34 and 25/40 of the wrong answers): the compression step is itself
unstable, so the compressed path is not only wrong more often, it is not repeatable. B and C did not
move. Files: `fr-events-v4-mini-100v3-20261002-r{2,3}.rescored.json`, `fr-mini-100v3-20261002-r{2,3}.json`.

## 3. What this does and does not add

Adds: an edge-class data point for the headline (size-independence under the layer) and a variance
table for the Q&A ("one run?"). Does not add: a new model family (nano is OpenAI's smallest, not an
open-weights 7B — say "the smallest model we could buy", not "an edge model"); three-judge panels
on the nano answers (not run); any change to the 21–22.09 numbers.

## 4. Figures

`talk-figures-20261002/fig1-evidence-path.*` now carries the nano bars with the footnote above;
`fig2-agreement.*` and `fig3-tomorrow.*` are unchanged in substance. Script: `make_figures.py`
(numbers from TALK-PACK §5; nano from `extra_models.json`).

## 5. A calibrated decision model as the fourth judge — TypeSafe Jev (jev-1.13.0, 2 October 2026)

Jev (TypeSafe "System One", launched 16.09.2026) returns typed decisions with calibrated probabilities
(RLCD-trained), not text. It was asked the same question as the three LLM judges over the same stored
gpt-5.4 answers and the same evidence per condition, as a `choice` over {supported, unsupported,
uncertain} (`smoke-tests-20260921/jev_judge.py`; verdicts, probabilities and raw responses in
`fr-judge-jev-fr-gpt54-100v3-20260921.json`, report `.report.json`). 300 verdicts, 604,586 input
tokens, **$0.025**, ≈ 90 seconds end to end.

| Condition | wrong answers | Jev certifies (supported) | mean P(supported) on wrong / on right | wrong answers the 3 LLM judges passed unanimously | of which Jev does NOT certify |
| --- | --- | --- | --- | --- | --- |
| A compressed (96 with answers) | 19 | **10** | 0.53 / 0.78 | 9 | **1** |
| B today's version | 97 | 2 | 0.07 / 0.65 | 2 | 1 |
| C as-of version | 9 | **9** | **0.89** / 0.93 | 5 | 0 |

Calibration on condition A (P(supported) bin → correct share): 0.8–1.0 → 47/54 (87 %); 0.6–0.8 → 15/18;
0.4–0.6 → 7/9; below 0.4 → 8/15. The probabilities are roughly honest about *what Jev was shown*: on the
compressed intermediate it is less sure of wrong answers (0.53) than of right ones (0.78), and still
certifies 10 of 19 and 8 of the 9 invisible lies; on the as-of version the 9 wrong answers (date/version
reasoning errors of the answerer) are certified at 0.89 — indistinguishable from right ones (0.93).

Reading: **calibration is honesty about the input, not about the lost original.** A model built to be
honest about its uncertainty, the fastest and cheapest judge we ran, signs the same invisible lies as the
three frontier LLMs. The resolved value catches all 9 of them (§5.6 of the pack) with no model at all.
This is the cleanest form of the title's answer: who verifies the verifier — not a better, faster or
more honest model; the data.

Do not say: "Jev is worse than X" (its acceptance of visible staleness, 2/97, is as good as the best LLM
judge); "Jev hallucinates" (it does not produce text). Say: *even a calibrated decision model signs the
lie it cannot see.* Limits: one run; one prompt wording (French question, French evidence); Jev's
32k-token window was never exceeded (max 24k chars evidence).
