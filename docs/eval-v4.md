# Eval set v4: a 125-question ruler for retrieval

Written as part of Phase 1 of `docs/upgrade/DEEPSEEK_BRIEF.md`. The point of v4 is that v3 has
30 questions (one question is 3.3 points of recall) and its questions were generated from headings
("Where is X documented?"), so it measures the retriever on its own vocabulary. v4 holds real
user-style questions with ground truth taken from the corpus, not from what the retriever returns.

## Files

| file | split | questions | sha256 |
|---|---|---|---|
| `tests/eval_v4_dev.yaml` | tunable, like `tests/golden.yaml` | 53 (48 scored + 5 negative) | `docs/eval-v4-dev.sha256` |
| `tests/eval_v4_heldout.yaml` | frozen, blind | 72 (65 scored + 7 negative) | `docs/eval-v4-heldout.sha256` |

Totals: 125 questions, 55 Vietnamese (44 %), 7 mixed Vietnamese-English, 63 English, 113 with an
`answer_snippet`, 12 negatives, all eight categories in both halves.

| category | dev | held-out | total |
|---|---|---|---|
| `param` | 9 | 13 | 22 |
| `code` | 9 | 13 | 22 |
| `wiki` | 9 | 13 | 22 |
| `protocol` | 8 | 9 | 17 |
| `hwdef` | 4 | 6 | 10 |
| `elrs_edgetx` | 4 | 6 | 10 |
| `troubleshoot` | 5 | 5 | 10 |
| `negative` | 5 | 7 | 12 |

## Protocol

1. Three writer agents worked in parallel on disjoint category groups (WP-B1 param/hwdef/protocol,
   WP-B2 code/wiki/elrs_edgetx, WP-B3 troubleshoot/negative plus Vietnamese with no diacritics).
   Each one was forbidden to call the retriever or read `query.py`; ground truth came from
   `data/corpus/` and read-only SQL over `documents`/`chunks`.
2. `research/validate_eval_set.py` checked every fragment: schema, unique ids, known category and
   language, that each `expect.path` exists for that source, that each `answer_snippet` occurs
   verbatim in a chunk of a matching document, duplicate and substring questions, and that a
   negative is not answerable from the corpus. All three fragments reported `errors: 0`.
3. `research/make_eval_v4.py` merged the fragments, validated the pool before splitting (so a
   cross-fragment duplicate can never land one copy in each half), and split it stratified by
   `(category, lang)` with seed `20261026`. The dev share is 53/125 (42 %).
4. The two SHA-256 files were written and committed. From then on the held-out file is only read by
   the evaluator with `--aggregate-only`; it is never opened as text and never tuned against.
5. The evaluator verifies the digest automatically: a mismatch exits non-zero and prints no
   question.

## Baseline (untouched retriever, `d0b7bd1` retriever code, 2026-10-26)

`python -m research.eval_retrieval --set tests/eval_v4_heldout.yaml --aggregate-only --no-floor`

```
recall@5 = 45/65 = 0.692
precision@1 = 24/65 = 0.369
MRR = 0.493
chunk-hit@5 = 0.369
negative-pass = 0.571
```

Per category and per language on the held-out half:

| group | n | recall@5 | P@1 | MRR | chunk-hit | neg-pass |
|---|---|---|---|---|---|---|
| code | 13 | 0.769 | 0.231 | 0.451 | 0.231 | - |
| elrs_edgetx | 6 | 0.833 | 0.500 | 0.639 | 0.667 | - |
| hwdef | 6 | 0.667 | 0.333 | 0.458 | 0.333 | - |
| negative | 7 | - | - | - | - | 0.571 |
| param | 13 | 0.462 | 0.231 | 0.297 | 0.077 | - |
| protocol | 9 | 0.556 | 0.111 | 0.248 | 0.222 | - |
| troubleshoot | 5 | 0.800 | 0.800 | 0.800 | 0.600 | - |
| wiki | 13 | 0.846 | 0.615 | 0.731 | 0.692 | - |
| en | 37 | 0.906 | 0.531 | 0.677 | 0.406 | 0.400 |
| mixed | 2 | 1.000 | 0.500 | 0.600 | 1.000 | - |
| vi | 33 | 0.452 | 0.194 | 0.297 | 0.290 | 1.000 |

Dev half (`baseline/dev.json`), for reference only: recall@5 0.583, P@1 0.375, MRR 0.452,
chunk-hit@5 0.312, negative-pass 0.200.

The floors in `eval_retrieval.py` stay at 0.8 for the tuned sets (`golden`, `heldout_v3`), which
still measure 1.000/0.767/0.859 and 0.933/0.833/0.868. v4 is measured, not gated, on that floor,
hence `--no-floor` in the baseline commands; Phase 2 ships a technique only if it beats these
numbers.

## What the baseline already says

- Vietnamese is the gap: 0.452 recall@5 against 0.906 for English on the same questions, and the
  `param` and `protocol` categories are weak in both languages.
- `chunk-hit@5` (0.369) is far below recall@5 (0.692): often the right file appears but the cited
  chunk is a neighbour paragraph, not the answer.
- `negative-pass = 0.571`: four of seven negatives still get an answer from the anchor gate. The
  Vietnamese negative set is better (0.750) but still lets 3 of 12 through.

## Errata

- 2026-10-26, V4-B2-024 path case. `tests/eval_v4_heldout.yaml` expected
  `common/source/docs/common-GPS-for-yaw.rst` while the corpus path is
  `common/source/docs/common-gps-for-yaw.rst`. The evaluator matches paths case-sensitively, but
  `validate_eval_set.py` used SQL `LIKE`, which folds ASCII case, so the validator accepted a path the
  evaluator would never hit. Fixed on both sides: the validator now uses `instr()` for paths (and has a
  test that rejects a case-only mismatch), and the one path was corrected byte-for-byte without
  touching any other line. Only that path was changed; no other held-out question was read.
  Frozen digest replaced: `cf9d2035058754723b67585f5e4f6286d5ddfccf64b83a35ed4c7b24a14803f4` becomes
  `5500cf0fbfc887b10147dcf040d176d78b5b904516938aa15357296fcdd458ed`. Effect on the baseline:
  recall@5 0.677 to 0.692, MRR 0.485 to 0.493 (the question was a miss only because of the case).
  `tests/eval_v4_dev.yaml` had no case mismatch, so its digest is unchanged.

## Vietnamese negative set

`tests/eval_v4_neg_vi.yaml` holds 12 Vietnamese and mixed questions the corpus cannot answer: weather,
prices, cooking, crypto, phone and router support, games, homework. Six are written without
diacritics, four with, two mixed. It is frozen by `docs/eval-v4-neg-vi.sha256`
(`15487469...`) and its writer never called the retriever.

`python -m research.eval_retrieval --set tests/eval_v4_neg_vi.yaml --aggregate-only --no-floor`:

```
negative-pass = 0.750
vi 0.800 (n=10), mixed 0.500 (n=2)
```

Nine of twelve are correctly refused; three still get an answer from the anchor gate. That is the same
failure mode as the held-out negatives (0.571), so the negative rate is the weakest Phase 1 number and
a Phase 2 target.


## Known limits

- The questions were written by agents, not harvested from real users, so "real phrasing" is
  simulated. They are independent of the retriever by construction, not by origin.
- `answer_snippet` rewards a chunk that contains the phrase; a correct answer paraphrasing it scores
  as a chunk miss.
- Nothing here measures answer quality, only which document and chunk surface. Safety behaviour is
  covered by the tool-level suites, not by this set.
- The writers worked in parallel, so the "8 Vietnamese no-diacritics variants of other writers'
  questions" of the brief became 8 independent no-diacritics questions in the same categories.
  Disclosed rather than hidden.
- One fragment arrived with 10 of 45 questions pointing at `ArduCopter/Parameters.cpp`; a second
  writer agent redistributed them to the library files that declare the same parameters (at most 3
  keep that file, distinct documents 20 to 25). That agent reported those Copter parameters exist
  only in `Parameters.cpp`, so the moved questions re-anchor to a library-declared parameter in the
  same topic instead of inventing a path.

## Phase 2 outcome

The frozen held-out split was used five times in total, each logged in
`docs/upgrade/DECISIONS.md`: the Phase 1 baseline, three Rung 1 builds (two rejected after a golden
regression and a determinism defect) and the Rung 2 dense candidate. Final numbers per configuration:

| configuration | recall@5 | P@1 | MRR | chunk-hit@5 | negative-pass |
|---|---|---|---|---|---|
| Phase 1 baseline | 0.692 | 0.369 | 0.493 | 0.369 | 0.571 |
| Rung 1 lexical, default | 0.723 | 0.323 | 0.475 | 0.369 | 0.571 |
| Rung 2 dense rerank, opt-in | 0.692 | 0.277 | 0.439 | 0.354 | 0.571 |

Vietnamese remains the weak language: recall@5 0.516 against 0.906 for English in the default build.
`docs/upgrade/UPGRADE_REPORT.md` has the per-category and per-language comparisons.
