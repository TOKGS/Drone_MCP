# Eval set v5-vi: a Vietnamese ruler for retrieval

Phase 3 of `docs/upgrade/PHASE3_BRIEF.md`, part B0. The v4 held-out split is spent (six runs, see
`docs/upgrade/DECISIONS.md`) and is now only a regression guard, so Phase 3 judges the Vietnamese
work on this new set. Everything here is Vietnamese or Vietnamese-English mixed, a large share
written without diacritics and in chat style, because that is how real users type.

## Files and counts

| file | split | questions | scored / negative | sha256 |
|---|---|---|---|---|
| `tests/eval_v5_vi_dev.yaml` | tunable, like `tests/golden.yaml` | 49 | 43 / 6 | `docs/eval-v5-vi-dev.sha256` |
| `tests/eval_v5_vi_heldout.yaml` | frozen, blind | 71 | 62 / 9 | `docs/eval-v5-vi-heldout.sha256` |

120 questions in total. 67 of them (55.8 %) are written without diacritics: 28 in dev, 39 in the
held-out half (the floor was 40 %). Language tags: `mixed` 95 (English identifiers inside the
Vietnamese question), `vi` 25. Every question is Vietnamese; none is English-only.

| category | dev | held-out | total | target |
|---|---|---|---|---|
| `param` | 8 | 12 | 20 | 20 |
| `code` | 9 | 11 | 20 | 20 |
| `wiki` | 8 | 12 | 20 | 20 |
| `protocol` | 6 | 9 | 15 | 15 |
| `hwdef` | 4 | 6 | 10 | 10 |
| `elrs_edgetx` | 4 | 6 | 10 | 10 |
| `troubleshoot` | 4 | 6 | 10 | 10 |
| `negative` | 6 | 9 | 15 | 15 |

The negatives are technical-sounding out-of-scope questions (PX4 parameter questions, Betaflight
GPS rescue, INAV tuning, Mission Planner's own scripting API, unpinned ArduPilot 3.x behaviour,
QGroundControl/DJI/Tello, KiCad, Keil) plus everyday topics (food, weather, football, prices,
streaming, houseplants). They exist because the dangerous failure of a retrieval change is a
confident answer to one of them.

## Protocol

1. Three fresh writer agents, disjoint category groups, each writing one scratch fragment. They were
   forbidden to call the retriever or read `query.py`, `glossary.vi-en.yaml`, or any v4 eval file;
   ground truth came from `data/corpus/` and read-only SQL over `documents`/`chunks`.
2. `research/validate_eval_set.py --strict-v5` checked every fragment: schema, unique ids, category,
   `lang` in {vi, mixed}, that a question flagged `diacritics: false` really carries no Vietnamese
   mark, that every `expect.path` exists case-sensitively, that every `answer_snippet` occurs
   verbatim in a chunk, duplicates and substrings, and that a negative is not answerable from the
   corpus. Fragments reported `errors: 0` (45 + 50 + 25 questions).
3. `research/make_eval_v5.py` merged the three fragments and, before splitting, cross-checked the
   pool against all three v4 files (137 questions) for re-use: two questions whose normalised token
   overlap was at least 60 % of the shorter one were rejected (`overlaps_v4`), which caught 6
   questions in the first pass and 3 after the first rewrite. The lead rewrote 5 unique questions
   (two of them twice) until the check reported 0 overlaps; the rewrites were confirmed by the
   validator, not by looking at the v4 questions.
4. The split is stratified by `(category, lang)` with seed `20261026`: dev 49 (40.8 %), held-out 71.
   The script prints counts, targets, the diacritics ratio and the two SHA-256 digests; it never
   prints a question.
5. Freeze: the digests live in `docs/eval-v5-vi-dev.sha256` and `docs/eval-v5-vi-heldout.sha256`
   (sha256sum layout). `research.eval_retrieval` finds them automatically and exits non-zero if a
   file changed. From the freeze on, the held-out file is read only by the evaluator with
   `--aggregate-only`; tuning happens on dev.

## Baseline (default build = Rung 1 BM25, no dense)

Both runs verified their digest (`sha256: verified against eval-v5-vi-dev.sha256 (0df27ec4b45aa208...)`
and `...eval-v5-vi-heldout.sha256 (19f0e46aaff2ae25...)`), raw output in
`docs/upgrade/baseline3/v5_vi_{dev,heldout}_default.txt`, JSON next to them.

| split | n | recall@5 | P@1 | MRR | chunk-hit@5 | negative-pass |
|---|---|---|---|---|---|---|
| dev (43 scored, 6 negative) | 49 | 0.488 | 0.256 | 0.354 | 0.302 | 0.500 |
| held-out (62 scored, 9 negative) | 71 | 0.581 | 0.387 | 0.447 | 0.242 | 0.556 |

Per category, default build (recall@5 / P@1 / MRR / chunk-hit; `neg-pass` for the negative row):

| category | dev n | dev | held-out n | held-out |
|---|---|---|---|---|
| `code` | 9 | 0.444 / 0.222 / 0.333 / 0.111 | 11 | 0.636 / 0.636 / 0.636 / 0.273 |
| `elrs_edgetx` | 4 | 0.750 / 0.750 / 0.750 / 0.750 | 6 | 0.667 / 0.333 / 0.458 / 0.167 |
| `hwdef` | 4 | 0.750 / 0.000 / 0.333 / 0.500 | 6 | 0.833 / 0.333 / 0.528 / 0.667 |
| `param` | 8 | 0.500 / 0.500 / 0.500 / 0.125 | 12 | 0.583 / 0.417 / 0.458 / 0.083 |
| `protocol` | 6 | 0.333 / 0.167 / 0.250 / 0.333 | 9 | 0.444 / 0.444 / 0.444 / 0.111 |
| `troubleshoot` | 4 | 0.750 / 0.250 / 0.425 / 0.750 | 6 | 0.667 / 0.500 / 0.556 / 0.500 |
| `wiki` | 8 | 0.250 / 0.000 / 0.087 / 0.125 | 12 | 0.417 / 0.083 / 0.161 / 0.167 |
| `negative` | 6 | neg-pass 0.500 | 9 | neg-pass 0.556 |

Per language, default build:

| group | dev n | dev (recall / P@1 / MRR) | held-out n | held-out |
|---|---|---|---|---|
| `mixed` | 36 | 0.500 / 0.278 / 0.376 | 54 | 0.593 / 0.389 / 0.451 |
| `vi` | 13 | 0.429 / 0.143 / 0.243 | 17 | 0.500 / 0.375 / 0.417 |

Per script, default build. `research/eval_retrieval.py` derives this group from the **question text**
(NFD combining marks, plus the letter d with a stroke), not from a declared field, and it never
changes the scoring: it is one more table in the printout and one more key in `--json`. The numbers
were added after the B0 baselines above were captured, so they are shown here for dev only; every
run from V1 on prints them.

| script | dev n | dev (recall / P@1 / MRR / chunk-hit) | negative-pass |
|---|---|---|---|
| `ascii-only` (no Vietnamese diacritics in the question) | 28 | 0.417 / 0.125 / 0.246 / 0.208 | 0.750 |
| `diacritics` | 21 | 0.579 / 0.421 / 0.491 / 0.421 | 0.000 |

The same split on `tests/eval_v4_dev.yaml` (tunable) is `ascii-only` n=34 0.867 / 0.567 / 0.687
against `diacritics` n=19 0.778 / 0.500 / 0.578. Read the two together: v4 dev is mostly English, so
its `ascii-only` group is easy text, while in v5 every question is Vietnamese and `ascii-only` means
"typed without diacritics", which is the hard half (recall@5 0.417 against 0.579). The split is
therefore about the keyboard, not about the language; `lang` remains the language axis.

## Baseline (opt-in dense rerank, `ARM_DENSE=1` on `data/exp/index.sqlite`)

`ARM_DATA_DIR=data\exp`, `ARM_MODEL_DIR=data\models\multilingual-e5-small`, one run per split, raw
output in `docs/upgrade/baseline3/v5_vi_{dev,heldout}_dense.txt` (`dense: loaded 86262 vectors
(126 MB) in 1.8-1.9s`).

| split | recall@5 | P@1 | MRR | chunk-hit@5 | negative-pass |
|---|---|---|---|---|---|
| dev | 0.512 | 0.279 | 0.381 | 0.326 | 0.500 |
| held-out | 0.581 | 0.387 | 0.444 | 0.242 | 0.556 |

Dense moves dev up by +0.024 recall@5 and +0.027 MRR, and the held-out split not at all (MRR
0.447 to 0.444). It stays where Phase 2 left it: off by default, measured here only as the
starting point for the Phase 3 ladder.

## Phase 3 shipped configuration (one held-out run)

The Phase 3 default (V1: chat normalisation, folded multi-word glossary match, out-of-scope refusal)
was measured **once** on the held-out split: `docs/upgrade/runs/final-v5_vi_heldout.txt`.

| split | recall@5 | P@1 | MRR | chunk-hit@5 | neg-pass |
|---|---|---|---|---|---|
| held-out, B0 baseline | 0.581 | 0.387 | 0.447 | 0.242 | 0.556 |
| held-out, shipped | 0.581 | 0.387 | 0.451 | 0.242 | 0.778 |

Per script on the shipped run: `ascii-only` n=39 0.529 / 0.382 / 0.439, `diacritics` n=32
0.643 / 0.393 / 0.465. So the no-diacritics half is still the weaker one, and it is the half the V1
normaliser was aimed at; the dev split moved more (`ascii-only` recall@5 0.417 -> 0.500, `diacritics`
0.579 unchanged) than the held-out split did. The ship bar (MRR +0.05) was not met; section 9 of
`PHASE3_REPORT.md` records that plainly.

## Companion set: v5-mention

`tests/eval_v5_mention.yaml` (18 positive questions, frozen by `docs/eval-v5-mention.sha256`) measures
a different property: the answer is in the corpus, the question asks about a corpus product
(ArduPilot, Copter, ExpressLRS, ELRS, EdgeTX, CRSF, MAVLink, Mission Planner, ...) and it also names
a product the corpus does not document (PX4, Betaflight, iNav, Cleanflight, KISS, QGroundControl).
Such a question must be answered, not refused. It exists because the first Phase 3 scope rule
refused on the foreign name alone and lost 9 of these 18; the counts and the three runs are in
`docs/upgrade/PHASE3_REPORT.md` section 3a. The set is not tuned: it was written, validated, frozen,
run once for the shipped configuration and once for the `master` baseline.

## What the baseline says about the ruler

- The set is harder than v4's Vietnamese subset: held-out recall@5 0.581 here against 0.516 there
  for `vi` in v4, but chunk-hit@5 is lower (0.242 against 0.290) and rank 1 is weaker on `wiki`
  (P@1 0.083). Chat-style questions with no diacritics are exactly where Rung 1's lexical path
  struggles.
- On dev, 25 of 49 questions miss, and **11 of those 43 positives are refused outright by the anchor
  gate** (`found:false`): the question is answerable from the corpus but carries no rare word and no
  `snake_case` symbol, so the gate rejects it. That is a retrieval defect the Phase 3 ladder has to
  move, not a defect in the questions.
- Three of the six dev negatives are answered instead of refused (Mission Planner scripting, an
  unpinned 3.x parameter, a football question), so negative-pass is 0.500 on dev and 0.556 on
  held-out. A retrieval change may not lower these numbers; it will be judged on all three negative
  sets (v5 dev, v4 `eval_v4_neg_vi`, v4 held-out).
- The held-out split scores **higher** than dev on every metric. With 43 and 62 scored questions the
  95 % interval on a recall of 0.5 is about ±0.15, so this is not a signal that the split leaked; it
  is a reminder that dev is for comparing configurations, not for reading absolute quality.
  Categories with n < 8 are flagged low-n in the ladder tables (`elrs_edgetx`, `hwdef`,
  `troubleshoot` on both splits, plus `protocol` on dev).
- One question in the held-out split is worth 1.6 points of recall@5, so a `+0.05` MRR ship bar needs
  about three questions of movement: the ladder must be read together with the per-category table.

## Limits

- Written by three agents in one session, then merged by one human-driven script; there is no
  second independent author review of the questions beyond the validator's structural checks.
- **5 of the 120 questions were rewritten by the lead** after the cross-set overlap check rejected
  them against a v4 question. The ids are `V5-W1-024`, `V5-W2-038`, `V5-W2-049`, `V5-W3-016`,
  `V5-W3-017`; the rewrite changed the topic or the wording (and, for two of them, the
  `expect`/`answer_snippet`), and every rewrite was re-validated. This is one more author for 4 % of
  the set, and it is reported so the audit can weigh it.
- Retrieval quality of the ground truth was not checked against a human expert: a passage that
  contains the snippet is treated as the answer, and 1-3 files are allowed per question.
- The no-diacritics share (55.8 %) and the chat-style share were counted from the `diacritics` flag
  and from a manual read of the fragments; the flag is enforced by the validator, the style is not.
- The negatives are 15 questions over nine subjects, so negative-pass moves in 0.11 steps
  (dev) and 0.11 steps (held-out); a small regression there can be one question.
- The held-out split was run once for the default build and once for the dense build. Every later
  configuration gets exactly one run, on the final tree only.
