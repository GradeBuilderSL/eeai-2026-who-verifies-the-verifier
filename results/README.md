# Results — every number in the talk, and the file it comes from

Run `python verify.py` at the repository root: it recomputes all of these from the files below with no model call.

| Said on stage | Value | File(s) |
| --- | --- | --- |
| Accuracy, gpt-5.4: compressed history → today's version → version in force → one typed figure per version + `resolve` | 77 → 3 → 91 → **99** / 100 | `fr-gpt54-100v3-20260921.json`, `fr-events-v4-gpt54-100v3-20260921.rescored.json` |
| Same, gpt-5.4-mini | 52 → 3 → 90 → **99** | `fr-mini-100v3-20260921.json`, `fr-events-v4-mini-100v3-20260921.rescored.json` |
| Same, gpt-5.4-nano (the smallest model we could buy) | 12\* → 3 → 91 → **97** (\*69 of 100 compressions returned nothing) | `fr-nano-100v3-20261002.json`, `fr-events-v4-nano-100v3-20261002.rescored.json` |
| Repeat runs, mini: D is reproducible, the compressed path is not | D 99 / 99 / 99; A 52 / 66 / 60 | `fr-mini-100v3-20261002-r{2,3}.json`, `fr-events-v4-mini-100v3-20261002-r{2,3}.rescored.json` |
| Three judges (mini / gpt-5.4 / deepseek) unanimously certify a WRONG gpt-5.4 answer | A compressed **9 of 19** (47 %) — the wrong answers the judges saw; 4 more compressions returned nothing and were never judged (9 of 23 = 39 % over all wrong) · B today's version **2 of 97** · C as-of 5 of 9 | `fr-judge-{mini,gpt54,deepseek}-g100v3-20260921.json`, `fr-judges-merged-g100v3.json` |
| Injected restriction drops: unanimous and wrong on the corrupted intermediate / on the original | **5 of 9**, **7 of 10** / 0 of 19, 0 of 17 | `seed-merged.json`, `seed-merged-ds.json`, `seed-{mini,gpt54,deepseek}-20260921.json` |
| Natural summarizer errors (AggreFact): false claims all three judges accepted | 0 of 28 (compressed), 2 of 32 (original) | `t2b-three-judges.json` |
| Placebo length: false accepts compressed / original / padded-to-length | 6 / 11 / 10 | `t3-placebo-length.json` |
| The resolved value catches every wrong answer the panel certified | **16 / 16**, 0 false alarms | `fr-events-v4-gpt54-100v3-20260921.rescored.json` + the judge files |
| Calibrated decision model (TypeSafe Jev, jev-1.13.0) as a 4th judge: certifies wrong answers | A 10 of 19 (mean P = 0.53) · C **9 of 9** (mean P = 0.89); rejects 1 of the 9 invisible lies the LLM panel passed | `fr-judge-jev-fr-gpt54-100v3-20260921.json`, `.report.json` |
| Tomorrow: future version recorded (47 pairs) — model right / `resolve` right | 38 / **45** | `fr-predict-gpt54-20260922.json` (mini: `fr-predict-mini-20260922.json`) |
| Tomorrow: future NOT recorded (78 pairs) — model invents a figure / `resolve` says "expired" | **72** / **72** | same |
| Event extraction → journal → `resolve` on 20 clean sources | 19/20 (mini), 18/20 (gpt-5.4) | `t4-events-{mini,gpt54}-20260921.json`, `t4-extract-*.json` |

File conventions: `fr-<model>-100v3-*.json` = conditions A/B/C (answers, the model's own verifier verdict, the
compressed text); `fr-events-v4-*.json` = condition D raw (one typed figure per version); `*.rescored.json` =
condition D after the deterministic rescoring (`scripts/fr_events_rescore.py`: thousands-separator and old-franc
fixes — the reported numbers); `fr-judge-*` = per-question verdicts of each judge. Every file keeps the full model
output, so any row can be read, not just counted. Cost of the whole study: about $35 of API use; the Jev run $0.025.
