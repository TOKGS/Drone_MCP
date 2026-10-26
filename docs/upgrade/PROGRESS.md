# Progress

Branch: `feat/eval-v4-hybrid-retrieval` (from `f54642e` on `master`, 2026-10-26).
Brief: `docs/upgrade/DEEPSEEK_BRIEF.md`. This file is the resume point: every task line records
status, commit, command and the key output line.

## Baseline (copied raw output)

`$env:PYTHONPATH = "D:\Skill_tulan\ardupilot-research-mcp\src"`, raw files in
`docs/upgrade/baseline/`.

`python -m pytest -q` (`baseline/pytest.txt`):

```
145 passed, 1 skipped in 42.93s
```

`python -m research.eval_retrieval --set tests/golden.yaml --aggregate-only` (`baseline/golden.txt`):

```
set=golden.yaml questions=30 k=5
recall@5 = 30/30 = 1.000
precision@1 = 23/30 = 0.767
MRR = 0.859
```

`python -m research.eval_retrieval --set tests/heldout_v3.yaml --aggregate-only` (`baseline/v3.txt`):

```
set=heldout_v3.yaml questions=30 k=5
recall@5 = 28/30 = 0.933
precision@1 = 25/30 = 0.833
MRR = 0.868
```

`python scripts\bench.py` (`baseline/bench.txt`):

```
search_docs           30     67.3    218.4    277.0
lookup_param           5     57.6     61.8     61.8
decode_crsf_frame      5      2.4      3.5      3.5
budget: search_docs p95 <= 400 ms, measured 218.4 ms
bench: PASS
```

### Deviations from the brief

- All four acceptance baselines reproduce exactly (145/1, 1.000, 0.933, p95 inside the budget).
- `bench.py` p50 moves run to run: 94.0 ms in the first run of this session, 67.3 ms in the second
  (p95 290.4 then 218.4). The brief's "p50 ~58 ms" is inside that spread. Budget still holds.
- README.md and README.vi.md still claim 141 tests; `scripts/check_readmes.py` expects 141 as well.
  Actual count is 145 passed + 1 skipped (146 collected). This is the stale number the brief mentions
  and it is WP-G work.
- `research/eval_retrieval.py` today accepts only `--set --k --verbose --aggregate-only`. It has no
  SHA-256 check and no `--json`/`--compare`. So the README sentence "the evaluator refuses to run if
  a set changed" is false today, and P1-A is real work, not a fixup.

## Feasibility verification (2026-10-26, before Phase 1)

Everything below was measured on this machine, not assumed.

Environment: Python 3.11.9, numpy 1.26.4, onnxruntime 1.20.1 (already installed), 8 CPU cores,
110.5 GB free on `D:`. `tokenizers` and `transformers` are absent.

Model `intfloat/multilingual-e5-small` (Hugging Face reachable, MIT license read in the model's own
`README.md`): `onnx/model.onnx` 448.5 MB (8.5 s to download), `tokenizer.json` 16.3 MB,
`sentencepiece.bpe.model` 4.8 MB, `hidden_size` 384, `max_position_embeddings` 512. Staged at
`data/models/multilingual-e5-small/` (gitignored). No quantised or fp16 ONNX exists in that repo
(404 on `model_quantized.onnx`, `model_fp16.onnx`), so quantisation would be our own step.

CPU throughput, 160 real chunks from `chunks.distilled`, 8 cores, `CPUExecutionProvider`:

```
tokens 256, batch 16 ->  8.8 chunks/s -> 164 min for 86 262 chunks
tokens 128, batch 32 -> 22.6 chunks/s ->  64 min for 86 262 chunks
tokens 128, batch 64 -> 16.7 chunks/s ->  86 min for 86 262 chunks
```

Vector table cost for 86 262 x 384: float32 126.4 MB, float16 63.2 MB, int8 31.6 MB. Index is
182.3 MB today, so float16 makes it about 246 MB. ONNX session load: 1.07 to 1.4 s, which is why the
brief wants a lazy first-query load.

The encoder needs `input_ids`, `attention_mask` **and** `token_type_ids`; pooling is mean over the
attention mask then L2 normalisation; e5 requires the `query: ` / `passage: ` prefixes.

Vietnamese probe (not retrieval evidence, only that the encoder separates the strings at all):
`cos("tá»‘c Ä‘á»™ bay", "toc do bay") = 0.823` versus `0.759` against "PX4 tuning" and `0.764` against
"land detector". Whether that helps retrieval is P1-F/P2's question, answered by the eval set only.

Alternative for the evidence-based model choice is reachable:
`sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` ONNX is 448.5 MB as well.

Gotcha recorded for this machine: `python -m pip install tokenizers` hangs for minutes, but the PyPI
index answers in 0.19 s and the cp311 wheel downloads with `urllib` in 0.37 s and installs with
`pip install --no-deps --target <dir>`. CI installs extras from PyPI normally; only this box needs the
wheel workaround (or one approved install outside the sandbox).

## Tasks

- [x] P1-A evaluator upgrade          owner: lead  commit: d0b7bd1  evidence: golden 1.000/0.767/0.859, v3 0.933/0.833/0.868, v3 sha256 verified, 10 new tests
- [x] P1-B question writers           owner: WP-B1 + WP-B2 + WP-B3 (subagents)  commit: 7d6a4c3  evidence: 45 + 50 + 30 = 125 questions, every fragment `errors: 0`
- [x] P1-C validation script          owner: lead  commit: 37c2c45  evidence: self-test fragment produced the 6 planted error codes, 7 tests
- [x] P1-D merge and split            owner: lead  commit: 7d6a4c3  evidence: 125 merged, dev 53 / held-out 72, stratified by (category, lang), seed 20261026
- [x] P1-E freeze                      owner: lead  commit: 7d6a4c3  evidence: docs/eval-v4-dev.sha256 `7f22f9cf...`, docs/eval-v4-heldout.sha256 `cf9d2035...`, scratch deleted (re-frozen as `5500cf0f...` in 1fe401b after one case-insensitive path was corrected)
- [x] P1-F baseline v4                owner: lead  commit: 7d6a4c3  evidence: docs/upgrade/baseline/{dev,heldout,golden,v3}.json + docs/eval-v4.md
- [x] Rung 0 baseline                 owner: lead  commit: 24a91fa  evidence: docs/upgrade/baseline/
- [x] Rung 1 lexical                  owner: lead  commit: ade40be (code) + 96ebc24  evidence: dev 0.583->0.833 recall, held-out 0.692->0.723, negatives held, bench 237.5 ms
- [x] Rung 2 dense + fusion           owner: lead  commit: c6527fd  evidence: built + measured; held-out 0.692/0.277/0.439 -> rejected as default, opt-in ARM_DENSE=1
- [x] Rung 3 rerank (optional)        owner: -    commit: -    evidence: skipped by the brief's own condition (only if Rung 2 helps); Rung 2 did not help
- [x] WP-G docs and gates             owner: lead  commit: (wp-g commit)  evidence: README.md + README.vi.md (184 tests, eval v4 table, optional dense section, 6 env vars, vector stage), CLAUDE.md, docs/eval-v4.md, docs/variant-4.6.md, UPGRADE_REPORT.md, all section-8 gates run

## Phase 1 result (raw)

`python -m research.eval_retrieval --set tests/eval_v4_heldout.yaml --aggregate-only --no-floor`
(raw file `baseline/heldout.txt`):

```
set=eval_v4_heldout.yaml questions=72 k=5
sha256: verified against eval-v4-heldout.sha256 (cf9d203505875472...)
recall@5 = 45/65 = 0.692
precision@1 = 24/65 = 0.369
MRR = 0.493
chunk-hit@5 = 0.369
negative-pass = 0.571
```

Dev half (`baseline/dev.txt`, tunable): recall@5 0.583, P@1 0.375, MRR 0.452, chunk-hit@5 0.312,
negative-pass 0.200. Per-category and per-language tables are in `docs/eval-v4.md`. The gap that
matters: held-out recall@5 is 0.452 for Vietnamese (n=33) against 0.906 for English (n=37).

Phase 1 exit criteria, each with the command that shows it:

- 125 questions, 55 Vietnamese (44 %), all eight categories in both halves, 12 negatives, 113 with
  `answer_snippet` (`validate_eval_set.py` counts per file).
- validator `errors: 0` on both files (runs above).
- two sha256 files committed; a mismatch exits non-zero and prints no question
  (`tests/test_eval_retrieval.py::test_sha_mismatch_raises_and_main_exits_nonzero`, proven on a
  temporary file, never by editing the real set).
- baseline JSONs in `docs/upgrade/baseline/`, `docs/eval-v4.md` written.
- `pytest` green, `check_readmes.py` green, `check_traceability.py` green (see the commit).

## Audit Phase 1 rework (2026-10-26, after the owner's audit)

- `PROGRESS.md` was 0 bytes at 84bee96: the BOM strip opened the file for writing before reading it.
  Restored from 7d6a4c3 with the freeze hash recorded and the byte count checked (8687 bytes,
  commit 5bbe588).
- `validate_eval_set.py` matched `expect.path` with SQL `LIKE`, which folds ASCII case, while the
  evaluator matches case-sensitively. It now uses `instr()` and a test rejects a case-only mismatch.
  That bug hid one wrong path in the frozen held-out set: V4-B2-024 expected
  `common-GPS-for-yaw.rst`, the corpus has `common-gps-for-yaw.rst`. Only that path line changed, the
  digest was re-frozen (`cf9d2035...` to `5500cf0f...`), errata are in `docs/eval-v4.md`, and the
  baseline was re-run: held-out recall@5 0.677 to 0.692, MRR 0.485 to 0.493.
- New `tests/eval_v4_neg_vi.yaml`: 12 Vietnamese and mixed out-of-scope questions, frozen by
  `docs/eval-v4-neg-vi.sha256` (`15487469...`), writer independent of the retriever. Baseline
  negative-pass 0.750 (vi 0.800, mixed 0.500), raw in `docs/upgrade/baseline/neg_vi.txt`.


## Rung 1 result (raw)

`tests/eval_v4_dev.yaml` (tunable): recall@5 0.583 -> 0.833, P@1 0.375 -> 0.542, MRR 0.452 -> 0.646,
chunk-hit@5 0.312 -> 0.354, negative-pass 0.200 (unchanged).

`tests/eval_v4_heldout.yaml` (measured once, for the final configuration):

```
recall@5 = 47/65 = 0.723      (baseline 0.692)
precision@1 = 21/65 = 0.323   (baseline 0.369)
MRR = 0.475                   (baseline 0.493)
chunk-hit@5 = 0.369           (baseline 0.369)
negative-pass = 0.571         (baseline 0.571, floor held)
```

`tests/eval_v4_neg_vi.yaml`: negative-pass 0.750 (baseline 0.750, floor held).
`tests/golden.yaml` 1.000/0.800/0.886 (was 1.000/0.767/0.859); `tests/heldout_v3.yaml`
0.933/0.833/0.868 unchanged; `scripts/bench.py` search_docs p95 237.5 ms, PASS.

Ablation per step and the rejected variants are in `docs/upgrade/rung1.md`; kept/rejected techniques
in `docs/upgrade/DECISIONS.md`; raw runs in `docs/upgrade/runs/rung1-*`.


## Rung 2 result (raw)

Built `research/build_vectors.py`, `chunk_vectors` (86 262 float16 vectors, 63.2 MB, 68.3 min at
21.0 chunks/s), `src/ardupilot_research_mcp/dense.py`, an opt-in rerank in `query.search`, the
`embeddings` extra and `index_status.dense`.

Dev ablation (tunable): RRF fusion families 0.604 to 0.688 recall@5, all worse than Rung 1's 0.833;
dense rerank alpha 2.0 gave 0.833 / 0.625 / 0.681 / 0.354.

Held-out, measured once for the kept candidate (dense on):

```
recall@5 = 45/65 = 0.692   (baseline 0.692, Rung 1 0.723)
precision@1 = 18/65 = 0.277 (baseline 0.369, Rung 1 0.323)
MRR = 0.439                (baseline 0.493, Rung 1 0.475)
chunk-hit@5 = 0.354        (baseline 0.369, Rung 1 0.369)
negative-pass = 0.571      (floor held; eval_v4_neg_vi 0.750, floor held)
```

Acceptance for a dense default needs held-out MRR >= 0.543; measured 0.439. So dense ships **off by
default** (`ARM_DENSE=1` opts in) and the BM25 path is untouched. Table with per-category and
per-language three-way comparison, the dev ablation ladder and the latency caveat:
`docs/upgrade/rung2.md`. Raw runs: `docs/upgrade/runs/rung2-*`.


## Phase 2 final gates (2026-10-26, raw)

```
pytest -q                                        184 passed, 1 skipped in 42.54s
check_readmes.py                                 readme check: PASS
check_traceability.py                            requirements=22 failing=0 known_tests=173, 185 collected
fidelity_scan.py                                 TOTAL 86262 0, fidelity: PASS
check_param_citations.py                         params checked: 5089, violations: 0
research.verify_citations                         chunk/line verification: PASS
research.audit_safety                            six inputs, four refusals, informational question not blocked
bench.py                                         search_docs p50 64.2 ms p95 222.1 ms max 325.3 ms, cold start 71 ms, PASS
mutation_check.py                                mutants=18 killed=17 survived=1 score=0.944, survivor M15, equivalent M12
golden.yaml                                      recall@5 1.000, P@1 0.800, MRR 0.886
heldout_v3.yaml                                  recall@5 0.933, P@1 0.833, MRR 0.868
eval_v4_heldout --compare baseline -> rung 1     flagged drops: 4
eval_v4_heldout --compare baseline -> rung 2     flagged drops: 8
blackbox_run.py --out docs/upgrade/blackbox_after cases_run=110
blackbox vs docs/blackbox/run3                   110 compared, 98 identical, 12 changed, 0 regressions
safety + offline suites, dense absent            35 passed
safety + offline suites, dense enabled           35 passed
dense requested on an index without vectors      BM25 answer, one warning naming the reason, state requested-but-unavailable
```

Raw files: `docs/upgrade/gates/*.txt`, blackbox payloads `docs/upgrade/blackbox_after/`.
The mutation survivor is disclosed, not hidden: `M15` removes the text identifier boost and is masked
by the path identifier boost added in Rung 1, so the score is 0.944 instead of the historical 1.000.
Full report: `docs/upgrade/UPGRADE_REPORT.md`.


## Decisions

- 2026-10-26: WP-G closed. Both READMEs carry the real test count, the eval v4 table and the
  optional dense section; CLAUDE.md documents the new files, the v4 rules, the extras and the
  fallback; UPGRADE_REPORT.md has the eleven sections. Bench re-measured on the quiet machine
  (p95 222.1 ms) after the loaded window that produced the earlier failure.
- 2026-10-26: Rung 2 built the dense path and rejected it as the default. Held-out MRR 0.439 against the 0.543 bar; the rerank is opt-in behind ARM_DENSE=1 and the default stays BM25 (docs/upgrade/rung2.md). Bench p95 could not be re-verified on this loaded machine: the Rung 1 code fails the same budget in interleaved runs, so no Rung 2 regression is claimed or inferred.
- 2026-10-26: Rung 1 kept four changes (glossary growth, parameter-declaration priority,
  Vietnamese anchor relaxation, test-harness penalty). Held-out P@1/MRR moved -0.015/-0.003
  while recall@5 rose +0.031; disclosed rather than hidden, details in docs/upgrade/rung1.md.
- 2026-10-26: Rung 1 also fixed a determinism defect found while re-checking: identifier passes
  iterated a set and ties broke on dict order, so PYTHONHASHSEED decided part of the ranking.
  Ties now break on cite_hash and a two-process test pins it (docs/upgrade/DECISIONS.md).
- 2026-10-26: work on `feat/eval-v4-hybrid-retrieval`, one commit per rung so each can be reverted.
- 2026-10-26: model staged at `data/models/multilingual-e5-small/` (gitignored) so the build stage can
  skip a 448.5 MB download while the pipeline is written. The build script must still download it when
  absent.
- 2026-10-26: `eval_retrieval` gained `--no-floor`. The 0.8 recall floor is an acceptance criterion
  for the tuned sets (`golden`, `heldout_v3`); v4 is a fresh measurement at 0.677, so the baseline
  commands and the CI report steps pass `--no-floor` instead of pretending the floor is met.
- 2026-10-26: `make_eval_v4.py` validates the merged pool before splitting (not just duplicate ids),
  so a cross-fragment duplicate can never put one copy in dev and one in held-out.
- 2026-10-26: the three writers ran in parallel, so the brief's "8 no-diacritics variants of other
  writers' questions" became 8 independent no-diacritics questions in the same categories. Disclosed
  in `docs/eval-v4.md` rather than hidden.
- 2026-10-26: WP-B1's fragment arrived with 10 of 45 questions pointing at
  `ArduCopter/Parameters.cpp`; a second writer agent redistributed them (at most 3 keep that file,
  distinct documents 20 to 25) and reported that those parameters exist only in that file, so the
  moved questions re-anchor to a library-declared parameter in the same topic.

## BLOCKERS

- none.

## Notes

- Sandbox limits that affect commands here: stdio smoke tests need `danger-full-access` (`WinError 5`
  on pipe creation), pip installs outside the workspace need escalation.
- Phase 1 is done; Phase 2 has not started. This branch is not pushed (the brief and GOAL forbid it).

