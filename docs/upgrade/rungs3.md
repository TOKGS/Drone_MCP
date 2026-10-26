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
