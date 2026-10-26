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
- [x] A-GATE pytest, check_readmes, check_traceability, fidelity, audit_safety  owner: lead  commit: <A-GATE>  evidence: 191 passed 1 skipped; readme PASS; requirements=22 failing=0; fidelity TOTAL 86262 0 PASS; audit_safety exit 0 for the six inputs (`gates/phase3_partA_*.txt`)
- [ ] B0-tools make_eval_v5 + validator cross-set overlap + tests        owner: lead  commit:  evidence:
- [ ] B0-w1 fragment param/hwdef/protocol                                owner: writer-1  commit:  evidence:
- [ ] B0-w2 fragment code/wiki/elrs_edgetx                               owner: writer-2  commit:  evidence:
- [ ] B0-w3 fragment troubleshoot/negative                               owner: writer-3  commit:  evidence:
- [ ] B0-merge validate, stratified split, freeze sha (dev + held-out)    owner: lead  commit:  evidence:
- [ ] B0-tamper evaluator refuses a tampered v5 set                       owner: lead  commit:  evidence:
- [ ] B0-baseline default and opt-in dense on both v5 splits -> baseline3/  owner: lead  commit:  evidence:
- [ ] B0-docs docs/eval-v5-vi.md                                         owner: lead  commit:  evidence:
- [ ] B1-V1 normaliser + mined glossary (vi)                              owner:  commit:  evidence:
- [ ] B1-V2 doc-level vectors as prior                                    owner:  commit:  evidence:
- [ ] B1-V3 expansion term weighting                                      owner:  commit:  evidence:
- [ ] B1-V4 256/512-token chunk rebuild (optional)                        owner:  commit:  evidence:
- [ ] B1-V5 recover the Rung 1 rank-1 regression on dev only              owner:  commit:  evidence:
- [ ] SHIP final run once per held-out set + gate section 8               owner:  commit:  evidence:
- [ ] REPORT docs/upgrade/PHASE3_REPORT.md, 12 sections                   owner:  commit:  evidence:

## Decisions (what you chose and why, one line each)

- Part A is done by the lead directly (small, single-file edits); only the v5-vi question writers are
  subagents, and they run in the shared workspace instead of separate worktrees because each owns
  exactly one new scratch file and the gitignored corpus/index can not be reached from a worktree.

## BLOCKERS

- (none)
