# Phase 3 ladder (V1 to V5)

One row per configuration. **Choices are made on dev sets only**: `tests/eval_v5_vi_dev.yaml` (49
questions, tunable) and `tests/eval_v4_dev.yaml` (53, tunable). `tests/eval_v5_vi_heldout.yaml` and
`tests/eval_v4_heldout.yaml` are run exactly once, for the configuration that is shipped. The
baseline is the Phase 2 default (Rung 1 BM25), recorded in `docs/upgrade/baseline3/`.

Reading a row: dev numbers are recall@5 / P@1 / MRR / chunk-hit@5 / negative-pass, with the sample
size, because one dev question is 2.3 points of recall (43 scored) and one negative is 16.7 points
(6 negatives).

## Baseline (Rung 1, no Phase 3 change)

| set | n | recall@5 | P@1 | MRR | chunk-hit | neg-pass |
|---|---|---|---|---|---|---|
| v5-vi dev | 49 | 0.488 | 0.256 | 0.354 | 0.302 | 0.500 |
| v4 dev | 53 | 0.833 | 0.542 | 0.646 | 0.354 | 0.200 |

## V1: Vietnamese chat normalisation, folded glossary match, out-of-scope refusal

Code: `src/ardupilot_research_mcp/vi.py` (new), `query.py` (`vi.normalise` before expansion, a
multi-word glossary key also matches with diacritics folded, `named_out_of_scope_product`),
`tests/test_vi.py` (new), `tests/test_query.py`.

What it does:

- chat spellings reach the canonical words before matching: "ko"/"kh" -> "không", "ntn" -> "như thế
  nào", "đc" -> "được"; ambiguous ones ("k", "dc", "vs", "j", "mn") only expand when the query has
  Vietnamese evidence, so "DC motor wiring" and "1k resistor" are left alone;
- a run of three or more identical lowercase letters collapses ("khongggg" -> "khong", "ĐẸPPP"
  untouched);
- a glossary key of two or more words now also fires when the *user* typed without diacritics
  ("khong arm duoc" fires the key "không arm được"); single-word keys keep the exact match, because
  folding "pin" or "bit" to ASCII would fire on an English word;
- a query that names an out-of-scope product with its own spelling (Betaflight, PX4, iNav, ...)
  returns `found:false` instead of nearby ArduPilot text. Case matters: "inav alt" is a PreArm
  parameter, so the lowercase spelling is not the product.

| set | n | recall@5 | P@1 | MRR | chunk-hit | neg-pass | delta vs baseline (recall / MRR) |
|---|---|---|---|---|---|---|---|
| v5-vi dev | 49 | 0.535 | 0.279 | 0.389 | 0.326 | 0.500 | +0.047 / +0.035 |
| v4 dev | 53 | 0.833 | 0.542 | 0.645 | 0.375 | 0.600 | 0.000 / -0.001 |
| v4 `eval_v4_neg_vi` | 12 | - | - | - | - | 0.750 | unchanged |
| golden | 30 | 1.000 | 0.800 | 0.881 | - | - | 0.000 / -0.005 |
| heldout v3 | 30 | 0.933 | 0.833 | 0.868 | - | - | 0.000 / 0.000 |

**Decision: keep.** v5-vi dev MRR and recall both rose, negative-pass did not fall on any negative
set (v4 dev rose because of the scope refusal), golden stays inside the 0.01 tolerance, v3 is
identical. Raw output: `docs/upgrade/runs/v1-*.txt`, JSON next to them.

Rejected inside V1: adding the ASCII Vietnamese function words ("bao", "nhieu", "vay", "nhu", ...)
to `STOPWORDS`. It raised the anchor gate's support ratio and bought three dev questions
(v5-vi dev recall 0.535 -> 0.605, MRR 0.448), but it also let out-of-scope questions through:
v5-vi dev negative-pass 0.500 -> 0.333 and `eval_v4_neg_vi` 0.750 -> 0.583. Measurement of the
anchor statistics showed why no threshold can separate the two: "schedulr loop doi j truoc khi chay
task" and a Genshin Impact question both come out at weight 3.25, support 0.54, three strong anchors.
The keep rule says negative-pass may not fall, so the stopword widening is reverted, with the numbers
left here.

## V2: document-level semantic prior (one vector per document)

Code: `research/build_doc_vectors.py` (new, 7 356 documents, 2.8 min, 5.4 MB float16),
`dense.docs_available` / `dense.docs_requested` / `dense.search_docs`, `query.DOC_PRIOR_WEIGHT`.
The query side is **off by default and also off under `ARM_DENSE=1`**: it needs `ARM_DOC_PRIOR=1`.
Corpus text for a document is its path with separators turned into spaces plus every distinct
heading path its chunks carry. The prior subtracts `DOC_PRIOR_WEIGHT * cosine` from every chunk of a
matching document; it never adds a candidate.

Measured on both dev sets, all with `ARM_DENSE=1` on the experiment index (`data/exp/index.sqlite`,
which holds the 86 262 chunk vectors and the 7 356 document vectors):

| configuration | v5-vi dev recall@5 | v5-vi dev MRR | v4 dev recall@5 | v4 dev MRR |
|---|---|---|---|---|
| BM25 + V1 (default) | 0.535 | 0.389 | 0.833 | 0.645 |
| chunk rerank only | 0.558 | 0.416 | 0.833 | 0.680 |
| chunk rerank + document prior (weight 2.0) | 0.535 | 0.408 | 0.812 | 0.686 |
| chunk rerank + document prior (weight 0.5) | 0.558 | 0.405 | 0.812 | 0.686 |

The prior costs recall on both sets and costs MRR on v5-vi dev; a lower weight does not help. The
document text is path vocabulary plus headings, which is thin evidence next to a chunk that spells
the question, so the prior mostly reorders documents that were already close. **Decision: rejected
as the default; the code stays behind `ARM_DOC_PRIOR=1` so the measurement can be repeated.** Raw
output: `docs/upgrade/runs/v2-*.txt`.

Worth recording: with the V1 normalisation in place, the chunk-level dense rerank (Rung 2, opt-in)
now beats BM25 on v5-vi dev (0.558 / 0.416 against 0.535 / 0.389). It stays off by default because
Phase 2's held-out run and the model dependency (448 MB) did not clear the ship bar, and this Phase 3
measurement is dev-only.

## V3: expansion term weighting

Code: `query.py`, the FTS tokens fall back to the original query when one of the user's own words is
index vocabulary (the translation only exists to reach words the corpus can match).

| set | recall@5 | P@1 | MRR | chunk-hit | neg-pass |
|---|---|---|---|---|---|
| v5-vi dev | 0.512 (was 0.535) | 0.279 | 0.378 (was 0.389) | 0.326 | 0.500 |
| v4 dev | 0.708 (was 0.833) | 0.500 | 0.577 (was 0.645) | 0.354 | 0.600 |
| golden | 0.967 (was 1.000) | 0.800 | 0.859 (was 0.881) | - | - |
| heldout v3 | 0.933 | 0.833 | 0.868 | - | - |

It removes the expansion terms from exactly the queries where they were still doing work. **Decision:
rejected**, reverted; the measurement is in this row and in the V1 commit message trail.

## V4: chunk vectors at 256 or 512 tokens

**Not attempted.** The estimate is measured, not guessed: 128 tokens ran at 21.0 chunks/s (68 min for
86 262 chunks), 256 tokens at 8.8 chunks/s (164 min) on this machine. The build would also have to be
re-run on a fresh experiment copy, and nothing in V1/V2/V3 suggests that a longer chunk window is the
limiter: the misses are documents that the BM25 candidate set never contained and questions the anchor
gate refuses, not chunks whose tail was cut. Recorded instead of run, with the wall-clock estimate.

## V5: recover the Rung 1 rank-1 regression (`elrs_edgetx`, `troubleshoot`, `wiki`)

Rung 1 pushed a parameter's declaring chunk to rank 1 for every query that named a parameter, which
moved `ArduCopter/Parameters.cpp` above the wiki page that answers a procedure question. The tested
rule was to keep the declaration priority only for a parameter-shaped query: two or fewer content
tokens, or an explicit declaration/default/meaning word.

| set | recall@5 | P@1 | MRR | chunk-hit | neg-pass |
|---|---|---|---|---|---|
| v5-vi dev | 0.442 (was 0.535) | 0.186 | 0.290 | 0.302 | 0.500 |
| v4 dev | 0.771 (was 0.833) | 0.500 | 0.593 | 0.375 | 0.600 |

It was much worse everywhere: the declaration priority is doing real work for the parameter category,
and the rank-1 losses Rung 1 caused are smaller than the losses its removal creates. **Decision:
rejected**, reverted. The Rung 1 regression on those categories therefore stays; it is a known limit
in the report, not a fixed item.

## Final configuration: one run per frozen set

The shipped configuration is the V1 change only: BM25 with the Vietnamese normalisation, the folded
multi-word glossary match and the out-of-scope refusal. Dense stays opt-in (`ARM_DENSE=1`) and the
document prior stays behind `ARM_DOC_PRIOR=1`.

`python -m research.eval_retrieval --set tests/eval_v5_vi_heldout.yaml --aggregate-only --no-floor`
(`docs/upgrade/runs/final-v5_vi_heldout.txt`, run once):

| split | n | recall@5 | P@1 | MRR | chunk-hit@5 | neg-pass |
|---|---|---|---|---|---|---|
| v5-vi held-out, baseline (B0) | 71 | 0.581 | 0.387 | 0.447 | 0.242 | 0.556 |
| v5-vi held-out, shipped | 71 | 0.581 | 0.387 | 0.451 | 0.242 | 0.778 |

Per category, shipped against baseline (recall@5 / MRR): `code` 0.636/0.636 unchanged, `elrs_edgetx`
0.667/0.458 unchanged, `hwdef` 0.833/0.528 unchanged, `param` 0.583/0.458 -> 0.479 (MRR +0.021),
`protocol` 0.444/0.444 unchanged, `troubleshoot` 0.667/0.556 unchanged, `wiki` 0.417/0.161 unchanged,
`negative` 0.556 -> 0.778. No category lost recall@5; `param` is the only positive category that
moved, and it moved up. Sample sizes are 6 to 12 per category, so 0.083 steps.

The v4 guard sets, one run each (`docs/upgrade/runs/final-v4_*.txt`):

| set | recall@5 | P@1 | MRR | neg-pass | floor |
|---|---|---|---|---|---|
| `eval_v4_heldout` (guard) | 0.738 (Rung 1: 0.723) | 0.323 | 0.482 (0.475) | 0.714 (0.571) | recall 0.70, MRR 0.45, neg 0.571 |
| `eval_v4_neg_vi` | - | - | - | 0.750 (=) | 0.750 |

**Ship bar, as written: not met.** It asks for `MRR +0.05` on v5-vi held-out; the shipped
configuration measured **+0.004** (0.447 -> 0.451) with recall unchanged. The rest of the bar holds
(no category lost 0.05, all v4 guard floors cleared, negative-pass rose sharply), and the release
notes say so instead of claiming a win. Section 9 of `PHASE3_REPORT.md` records why the change is
still the default: it is input normalisation plus an out-of-scope refusal, it is what lifts
negative-pass from 0.556 to 0.778 on the new held-out set, and every alternative measured worse.
