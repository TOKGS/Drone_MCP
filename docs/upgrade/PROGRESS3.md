# Progress: Phase 3

Branch `feat/phase3-vi-retrieval`, created from `master` at `518addc` (the commit that added
`GOAL3.md` and `PHASE3_BRIEF.md`; the Phase 2 merge it sits on is `235b36b`). The old
`docs/upgrade/PROGRESS.md` is history and is not edited.

## Baseline (copied raw output)

Section 0 verification, before any change:

```
python -m pytest -q
184 passed, 1 skipped in 38.14s
```

```
python -m research.eval_retrieval --set tests/eval_v4_heldout.yaml --aggregate-only --no-floor
# this was run 7 of the set (budget: 6 spent in Phase 2); the tail printed now is identical to the
# committed run of the same configuration. Header from docs/upgrade/runs/rung1-heldout.txt:
recall@5 = 47/65 = 0.723   precision@1 = 21/65 = 0.323   MRR = 0.475
chunk-hit@5 = 0.369        negative-pass = 0.571
per language: en n=37 0.906/0.531/0.678 ; vi n=33 0.516/0.097/0.256 ; mixed n=2 1.000/0.500/0.600
```

```
python -m research.eval_retrieval --set tests/eval_v4_neg_vi.yaml --aggregate-only --no-floor
negative 12  neg-pass 0.750       per language: vi n=10 0.800 ; mixed n=2 0.500
```

```
python scripts/bench.py
search_docs 30  p50 67.2  p95 232.3  max 338.6 ms
cold start (first search, includes model + vector load): 79 ms
budget: search_docs p95 <= 400 ms, measured 232.3 ms      bench: PASS
```

## Tasks

- [x] A1 README status numbers + checker that catches a stale test count   owner: lead  commit: 4d2f6c2  evidence: `readme check: PASS` (collected 192, accepted 191/192); planted `141` fails, `tests/test_check_readmes.py` 6 tests
- [x] A2 UPGRADE_REPORT mutation count consistent                         owner: lead  commit: a9f1475  evidence: summary now quotes `mutants=18 killed=17 survived=1 errors=0 equivalent=1 score=0.944`
- [x] A3 mutant M15: kill with a test or flag equivalent                  owner: lead  commit: 2fc598a  evidence: `mutants=18 killed=18 survived=0 errors=0 equivalent=1 score=1.000`; the new test fails when the `6.0` boost is zeroed
- [x] A4 E_INFO_02 cap investigation, decision recorded                   owner: lead  commit: da1761e  evidence: payload has no `results` key, 10 274 B against a 24 576 B cap, no `truncated_by_guard`; decision in `DECISIONS.md`
- [x] A5 experiment index paragraph (docs)                                owner: lead  commit: 6c8121a  evidence: `docs/upgrade/rung2.md` section "Experiment index"
- [x] A6 eval-v4 regression-guard note                                    owner: lead  commit: d2f5b4a  evidence: note at the top of `docs/eval-v4.md`
- [x] A-GATE pytest, check_readmes, check_traceability, fidelity, audit_safety  owner: lead  commit: 42e40dd  evidence: 191 passed 1 skipped; readme PASS; requirements=22 failing=0; fidelity TOTAL 86262 0 PASS; audit_safety exit 0 for the six inputs (`gates/phase3_partA_*.txt`)
- [x] B0-tools make_eval_v5 + validator cross-set overlap + tests        owner: lead  commit: 59ad485  evidence: `--strict-v5` + `--cross-check` in `research/validate_eval_set.py`, `research/make_eval_v5.py`, 5 tests in `tests/test_eval_v5.py`
- [x] B0-w1 fragment param/hwdef/protocol                                owner: writer-1  commit: 59ad485  evidence: 45 questions (20/10/15), diacritics_free=25, `errors: 0`
- [x] B0-w2 fragment code/wiki/elrs_edgetx                               owner: writer-2  commit: 59ad485  evidence: 50 questions (20/20/10), diacritics_free=28, `errors: 0`
- [x] B0-w3 fragment troubleshoot/negative                               owner: writer-3  commit: 59ad485  evidence: 25 questions (10/15), diacritics_free=14, `errors: 0`
- [x] B0-merge validate, stratified split, freeze sha (dev + held-out)    owner: lead  commit: 59ad485  evidence: 120 questions, dev 49 / held-out 71, no-diacritics 67 (55.8%), negatives 15, overlaps 6 to 3 to 0; sha `0df27ec4...` / `19f0e46a...`
- [x] B0-tamper evaluator refuses a tampered v5 set                       owner: lead  commit: 59ad485  evidence: `test_the_v5_sets_are_pinned` and `test_a_tampered_v5_copy_is_refused` (12 passed in `tests/test_eval_retrieval.py`); both baseline runs printed `sha256: verified`
- [x] B0-baseline default and opt-in dense on both v5 splits -> baseline3/  owner: lead  commit: 1a1730f  evidence: dev default 0.488/0.256/0.354/0.302/0.500, dev dense 0.512/0.279/0.381/0.326/0.500; held-out default 0.581/0.387/0.447/0.242/0.556, held-out dense 0.581/0.387/0.444/0.242/0.556
- [x] B0-docs docs/eval-v5-vi.md                                         owner: lead  commit: 59ad485  evidence: protocol, counts, both baseline tables, what the ruler says, limits
- [x] B1-V1 normaliser + folded glossary + out-of-scope refusal           owner: lead  commit: ef447bf  evidence: v5-vi dev 0.535/0.279/0.389, v4 dev 0.833/0.645, neg 0.500/0.600; kept
- [x] B1-V2 doc-level vectors as prior                                    owner: lead  commit: 617e9b5  evidence: 7 356 docs, 2.8 min, 5.4 MB; prior behind ARM_DOC_PRIOR=1; v5 dev MRR 0.416 -> 0.408 and recall 0.558 -> 0.535, rejected
- [x] B1-V3 expansion term weighting                                      owner: lead  commit: 617e9b5  evidence: v4 dev recall 0.833 -> 0.708, golden 1.000 -> 0.967; rejected and reverted
- [x] B1-V4 256/512-token chunk rebuild (optional)                        owner: lead  commit: none  evidence: not attempted; measured estimate 164 min at 256 tokens (8.8 chunks/s)
- [x] B1-V5 recover the Rung 1 rank-1 regression on dev only              owner: lead  commit: 617e9b5  evidence: v5 dev 0.535 -> 0.442, v4 dev 0.833 -> 0.771; rejected and reverted
- [x] SHIP final run once per held-out set + gate section 8               owner: lead  commit: ca52859  evidence: v5 held-out 0.581/0.387/0.451/0.242/0.778, v4 held-out 0.738/0.323/0.482/0.369/0.714, neg_vi 0.750; all gates in gates/phase3_*
- [x] REPORT docs/upgrade/PHASE3_REPORT.md, 12 sections                   owner: lead  commit: ca52859  evidence: 12 sections, ship bar disclosed as not met

## Decisions (what you chose and why, one line each)

- Part A is done by the lead directly (small, single-file edits); only the v5-vi question writers are
  subagents, and they run in the shared workspace instead of separate worktrees because each owns
  exactly one new scratch file and the gitignored corpus/index can not be reached from a worktree.
- v5-vi: the cross-set overlap check rejected 9 questions over two passes (6 then 3); the lead
  rewrote 5 of them (two twice) by changing the topic or the wording, and never looked at a v4
  held-out question. Recorded in `docs/eval-v5-vi.md`.
- v5-vi baseline: the held-out split was measured twice on purpose, once for the default build and
  once for `ARM_DENSE=1`, which is what B0 asks for; every later configuration gets one run.

## BLOCKERS

- (none)

## B0 evidence (raw)

```
python -m research.validate_eval_set --set tests/eval_v5_vi_dev.yaml --strict-v5 --cross-check ...
cross-check: 49 questions vs 137 from 3 set(s), overlaps=0
set=eval_v5_vi_dev.yaml questions=49 db=checked
categories: code=9 elrs_edgetx=4 hwdef=4 negative=6 param=8 protocol=6 troubleshoot=4 wiki=8
langs: mixed=36 vi=13
snippets=43 negatives=6 diacritics_false=28
errors: 0

python -m research.validate_eval_set --set tests/eval_v5_vi_heldout.yaml --strict-v5 --cross-check ...
cross-check: 71 questions vs 137 from 3 set(s), overlaps=0
set=eval_v5_vi_heldout.yaml questions=71 db=checked
categories: code=11 elrs_edgetx=6 hwdef=6 negative=9 param=12 protocol=9 troubleshoot=6 wiki=12
langs: mixed=54 vi=17
snippets=62 negatives=9 diacritics_false=39
errors: 0

python -m research.make_eval_v5 --fragment docs/upgrade/scratch/q5_w1.yaml --fragment ... --fragment ...
fragments=3 questions=120 dev=49 heldout=71 cross-checked=137
(param 20, code 20, protocol 15, hwdef 10, wiki 20, elrs_edgetx 10, troubleshoot 10, negative 15)
no diacritics: total=67 (55.8%) dev=28 heldout=39  ok (floor 40%)
negatives: 15  ok (floor 15)
sha256 eval_v5_vi_dev.yaml = 0df27ec4b45aa208b5618ba22d69955301d47979504b9ad6caeb3902e55cdf3d
sha256 eval_v5_vi_heldout.yaml = 19f0e46aaff2ae25b120bebf74bd6a610121f3e689d1510ae3962d2dae3412a3
```

```
docs/upgrade/baseline3/v5_vi_dev_default.txt
sha256: verified against eval-v5-vi-dev.sha256 (0df27ec4b45aa208...)
recall@5 = 21/43 = 0.488   P@1 = 0.256   MRR = 0.354   chunk-hit@5 = 0.302   negative-pass = 0.500
docs/upgrade/baseline3/v5_vi_heldout_default.txt
sha256: verified against eval-v5-vi-heldout.sha256 (19f0e46aaff2ae25...)
recall@5 = 36/62 = 0.581   P@1 = 0.387   MRR = 0.447   chunk-hit@5 = 0.242   negative-pass = 0.556
docs/upgrade/baseline3/v5_vi_dev_dense.txt
recall@5 = 0.512   P@1 = 0.279   MRR = 0.381   chunk-hit@5 = 0.326   negative-pass = 0.500
docs/upgrade/baseline3/v5_vi_heldout_dense.txt
recall@5 = 0.581   P@1 = 0.387   MRR = 0.444   chunk-hit@5 = 0.242   negative-pass = 0.556
```

## Phase 3 final results (raw in docs/upgrade/runs/final-*.txt)

```
python -m research.eval_retrieval --set tests/eval_v5_vi_heldout.yaml --aggregate-only --no-floor
recall@5 = 36/62 = 0.581   precision@1 = 24/62 = 0.387   MRR = 0.451
chunk-hit@5 = 0.242        negative-pass = 0.778        (B0 baseline: 0.581/0.387/0.447/0.242/0.556)

python -m research.eval_retrieval --set tests/eval_v4_heldout.yaml --aggregate-only --no-floor
recall@5 = 48/65 = 0.738   precision@1 = 21/65 = 0.323   MRR = 0.482
chunk-hit@5 = 0.369        negative-pass = 0.714        (Rung 1: 0.723/0.323/0.475/0.369/0.571)

python -m research.eval_retrieval --set tests/eval_v4_neg_vi.yaml --aggregate-only --no-floor
negative-pass = 0.750                                   (unchanged)
```

Ship bar (MRR +0.05 on v5-vi held-out) measured +0.004: **not met**, disclosed in section 9 of
`PHASE3_REPORT.md`.
