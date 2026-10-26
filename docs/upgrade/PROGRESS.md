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
`cos("tốc độ bay", "toc do bay") = 0.823` versus `0.759` against "PX4 tuning" and `0.764` against
"land detector". Whether that helps retrieval is P1-F/P2's question, answered by the eval set only.

Alternative for the evidence-based model choice is reachable:
`sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` ONNX is 448.5 MB as well.

Gotcha recorded for this machine: `python -m pip install tokenizers` hangs for minutes, but the PyPI
index answers in 0.19 s and the cp311 wheel downloads with `urllib` in 0.37 s and installs with
`pip install --no-deps --target <dir>`. CI installs extras from PyPI normally; only this box needs the
wheel workaround (or one approved install outside the sandbox).

## Tasks

- [x] P1-A evaluator upgrade          owner: lead  commit: (this commit)  evidence: golden 1.000/0.767/0.859, v3 0.933/0.833/0.868, v3 sha256 verified, 10 new tests
- [ ] P1-B question writers           owner:      commit:      evidence:
- [x] P1-C validation script          owner: lead  commit: (this commit)  evidence: selftest fragment -> 6 expected error codes, 7 tests
- [ ] P1-D merge and split            owner: lead  script ready (research/make_eval_v4.py, 3 tests); split pending the writer fragments
- [ ] P1-E freeze                      owner:      commit:      evidence:
- [ ] P1-F baseline v4                owner:      commit:      evidence:
- [ ] Rung 0 baseline                 owner:      commit:      evidence: docs/upgrade/baseline/
- [ ] Rung 1 lexical                  owner:      commit:      evidence:
- [ ] Rung 2 dense + fusion           owner:      commit:      evidence:
- [ ] Rung 3 rerank (optional)        owner:      commit:      evidence:
- [ ] WP-G docs and gates             owner:      commit:      evidence:

## Decisions

- 2026-10-26: work on `feat/eval-v4-hybrid-retrieval`, one commit per rung so each can be reverted.
- 2026-10-26: model staged at `data/models/multilingual-e5-small/` (gitignored) so the build stage can
  skip a 448.5 MB download while the pipeline is written. The build script must still download it when
  absent.

## BLOCKERS

- none yet.

## Notes

- Sandbox limits that affect commands here: stdio smoke tests need `danger-full-access` (`WinError 5`
  on pipe creation), pip installs outside the workspace need escalation.
