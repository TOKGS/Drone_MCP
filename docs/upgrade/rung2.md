# Rung 2: dense retrieval and fusion

Phase 2, Rung 2 of `docs/upgrade/DEEPSEEK_BRIEF.md` section 5. Built, measured, and **rejected as
the default**: the optional rerank is shipped behind `ARM_DENSE=1`, the BM25 ranking stays the
default, and this file records the numbers that led there.

## What was built

| piece | file | notes |
|---|---|---|
| vector build | `research/build_vectors.py` + a stage in `research/build_all.py` | embeds `chunks.distilled`, resumable by rowid, `--optional` so a missing model skips cleanly |
| vectors | `chunk_vectors(rowid, dim, vec)` + `chunk_vectors_meta` in `index.sqlite` | float16, 384 dims, 63.2 MB for 86 262 chunks |
| query side | `src/ardupilot_research_mcp/dense.py` | ONNX e5-small, lazy first-query load, in-process matrix cache, top-k by `argpartition` then a deterministic sort on `cite_hash` |
| fusion | `query._dense_reranked_scores` | cosine reranks the candidates BM25 already produced; it never adds a candidate |
| opt-in | `ARM_DENSE=1`, `ARM_MODEL_DIR` | unset means BM25 only, missing table/model/deps fall back silently |
| reporting | `index_status.dense` | `{present, vectors, dim, size_mb, model, built_at}` |
| extras | `pyproject.toml [project.optional-dependencies] embeddings` | `onnxruntime>=1.20`, `tokenizers>=0.20`, `numpy>=1.26` |

Model: `intfloat/multilingual-e5-small`, ONNX 448.5 MB, MIT (read in the model's own README, recorded
in `docs/license-notes.md`). Measured on this machine at 128 tokens and batch 32: **21.0 chunks/s,
68.3 min for 86 166 chunks**, index 182.3 MB to 249.9 MB. Cold start (first query loads the session
and the 126 MB float32 matrix): 6.7 s.

## Dev ablation (the tunable split)

Baseline is Rung 1: recall@5 0.833, P@1 0.542, MRR 0.646, chunk-hit 0.354.

| configuration | recall@5 | P@1 | MRR | chunk-hit | decision |
|---|---|---|---|---|---|
| RRF, dense weight 1.0, k=60, 50 candidates | 0.688 | 0.500 | 0.575 | 0.271 | worse |
| RRF, dense weight 0.2 | 0.604 | 0.458 | 0.512 | 0.229 | worse |
| RRF, dense weight 0.4 | 0.625 | 0.479 | 0.539 | 0.229 | worse |
| RRF, dense weight 0.6 | 0.667 | 0.500 | 0.574 | 0.229 | worse |
| RRF, similarity floor 0.80 | 0.688 | 0.500 | 0.575 | 0.271 | worse |
| RRF, similarity floor 0.85 | 0.646 | 0.479 | 0.540 | 0.271 | worse |
| RRF, similarity floor 0.88 | 0.604 | 0.438 | 0.503 | 0.271 | worse |
| dense adds candidates only | 0.667 | 0.500 | 0.565 | 0.292 | worse |
| rerank, alpha 1.0 | 0.833 | 0.625 | 0.691 | 0.333 | good |
| **rerank, alpha 2.5** | **0.833** | **0.625** | **0.692** | **0.333** | **chosen (alpha 2.0)** |
| rerank, alpha 5.0 | 0.833 | 0.604 | 0.684 | 0.312 | good, less |
| rerank, alpha 7.5 | 0.812 | 0.583 | 0.674 | 0.312 | worse |

Adding dense candidates to the list made the dev split clearly worse. Reranking the BM25 candidates
by cosine improved rank-1 precision and MRR without touching recall. The brief said to follow its
RRF architecture unless there is measured evidence for a change; this is that evidence, and
`DECISIONS.md` records it.

## Held-out (measured once, for the kept candidate: rerank alpha 2.0)

`python -m research.eval_retrieval --set tests/eval_v4_heldout.yaml --aggregate-only --no-floor`
with `ARM_DENSE=1` (`docs/upgrade/runs/rung2-heldout.txt`).

| metric | baseline (Phase 1) | Rung 1 | Rung 2 (dense on) |
|---|---|---|---|
| recall@5 | 0.692 | **0.723** | 0.692 |
| precision@1 | 0.369 | 0.323 | 0.277 |
| MRR | 0.493 | 0.475 | 0.439 |
| chunk-hit@5 | 0.369 | 0.369 | 0.354 |
| negative-pass (held-out) | 0.571 | 0.571 | 0.571 |
| negative-pass (`eval_v4_neg_vi`) | 0.750 | 0.750 | 0.750 |

Per category and per language (recall@5 / MRR):

| group | n | baseline | Rung 1 | Rung 2 |
|---|---|---|---|---|
| code | 13 | 0.769 / 0.451 | 0.846 / 0.522 | 0.846 / 0.487 |
| elrs_edgetx | 6 | 0.833 / 0.639 | 0.833 / 0.472 | 0.833 / 0.472 |
| hwdef | 6 | 0.667 / 0.458 | 0.667 / 0.458 | 0.500 / 0.389 |
| param | 13 | 0.462 / 0.297 | 0.538 / 0.442 | 0.538 / 0.391 |
| protocol | 9 | 0.556 / 0.248 | 0.556 / 0.248 | 0.444 / 0.217 |
| troubleshoot | 5 | 0.800 / 0.800 | 0.800 / 0.533 | 0.800 / 0.433 |
| wiki | 13 | 0.846 / 0.731 | 0.846 / 0.603 | 0.846 / 0.603 |
| en | 37 | 0.906 / 0.677 | 0.906 / 0.678 | 0.844 / 0.609 |
| mixed | 2 | 1.000 / 0.600 | 1.000 / 0.600 | 1.000 / 0.625 |
| vi | 33 | 0.452 / 0.297 | 0.516 / 0.256 | 0.516 / 0.251 |

Acceptance for shipping dense as the default is **not met**: held-out MRR would have to reach 0.543
(baseline + 0.05) and it measured 0.439; recall@5 also fell back from Rung 1's 0.723 to 0.692, and
hwdef and protocol lost more than 0.05 recall@5. Rung 2 therefore does not restore the categories
Rung 1 cost either: troubleshoot and wiki keep Rung 1's MRR level, hwdef and protocol get worse.

## Other gates

| command | result |
|---|---|
| `python -m pytest -q` | 180 passed, 1 skipped (9 dense tests) |
| `python scripts/check_readmes.py` | PASS |
| `python scripts/check_traceability.py` | 22 requirements, 0 failing |
| `python -m research.eval_retrieval --set tests/golden.yaml` (dense on) | 1.000 / 0.833 / 0.908 (baseline 1.000 / 0.767 / 0.859) |
| `python -m research.eval_retrieval --set tests/heldout_v3.yaml` (dense on) | 0.933 / 0.833 / 0.869 (baseline 0.933 / 0.833 / 0.868) |
| `scripts/bench.py` | NOT MEASURABLE right now, see below |

Bench caveat: the machine was heavily loaded for the whole final hour (the harness's own processes),
and the budget fails for the **Rung 1 code as well** on the same index: interleaved runs gave
p95 808 / 993 ms for Rung 1 and 761 / 670 ms for Rung 2 default, against 237.5 ms for Rung 1 on a
quiet machine earlier today. Dense on adds 64 to 90 ms of `dense.search` per query plus the 6.7 s
cold load. So: no regression attributable to Rung 2, but the 400 ms p95 claim cannot be re-verified
in this window and is reported as unverified rather than passed.

## Decision

Dense is **off by default**: `ARM_DENSE=1` opts in, everything else behaves exactly like Rung 1
(`tests/test_dense.py::test_dense_is_off_unless_arm_dense_is_set`). `data/index.sqlite` keeps no
vectors; the experiment vectors live in `data/exp/index.sqlite` (gitignored). To try it:

```powershell
python -m research.build_vectors --index data\index.sqlite   # 68 min, 63 MB
$env:ARM_DENSE = "1"
```

Reproduction of the measured candidate: `docs/upgrade/runs/rung2-*.txt`, JSON next to them.
