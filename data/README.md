# Data

## `fr-cases-100-v3.json` — 100 date-anchored questions on the versioned French tax code

Derived from **fiscal-fr-bench** (Cymbler, Guez, Fabre — ICML 2026 Workshop on AI for Law; repository
`rosecymbler/fiscal-fr-bench`, commit `6ca3807`): the "killer" R3 temporal-reasoning set (209 questions that every
frontier model gets wrong under static retrieval). We hash-picked 100 questions, at most 4 per article, over 33
articles (`scripts/fr_build.py`). For each question the file carries the benchmark's prompt, reference date,
canonical answer and scoring nuggets (regex / exact / numeric-with-tolerance), plus three evidence texts cut from
the benchmark's versioned corpus: `gold_text` (the version in force on the date), `current_text` (today's
version) and `history_text` (a bounded version history, at most 55,000 characters, always containing both).

Scoring is the benchmark's own: an answer is right when every required nugget matches. No LLM judge is involved
in any accuracy number.

**License and attribution.** The benchmark's data is CC BY 4.0 and requires attribution of the underlying
sources: legislation from the Légifrance API (DILA / PISTE) under *Licence Ouverte / Etalab 2.0*. The article
texts in this file are those public legal texts. Please cite the benchmark:

```bibtex
@inproceedings{fiscalqapro2026,
  title     = {Temporal Misgrounding in Legal RAG: A Versioned-Corpus Benchmark for French Tax Law},
  author    = {Cymbler, Rose and Guez, Daniel and Fabre, Laurent},
  booktitle = {ICML 2026 Workshop on AI for Law (AI4Law)},
  year      = {2026}
}
```

## `seed-qualifier-drop.json`, `seed-layered.json` — injected restriction drops (synthetic)

Twenty (plus eight layered) short business/regulatory statements, each with one critical restriction span (a
date, an interval, a cancellation, a scope) and a corrupted intermediate that drops or overrides it, plus a
date-free false claim and the as-of date. Written by us and by a model (`scripts/seed_author.py`,
`seed_rewrite.py`); gold by construction. These are the cases behind "unanimous and wrong 5 of 9 / 7 of 10".
CC BY 4.0.
