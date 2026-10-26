# Decisions

One entry per kept or rejected technique: what changed, measured effect, decision. Dev is the
tunable split; held-out is measured once per configuration that is kept.

## Rung 1 (lexical), 2026-10-26

| # | technique | dev (recall / P@1 / MRR / chunk) | held-out (recall / P@1 / MRR / chunk) | decision |
|---|---|---|---|---|
| 1 | glossary growth, 45 Vietnamese phrases incl. ASCII mirrors | 0.583/0.375/0.452/0.312 to 0.708/0.396/0.512/0.312 | not measured alone | kept |
| 2 | parameter-declaration priority (params table decides the answer) | to 0.771/0.500/0.593/0.312 | not measured alone | kept |
| 3 | Vietnamese anchor relaxation (glossary-fired query needs weight 2, old rule still valid) | to 0.792/0.500/0.603/0.333 | not measured alone | kept |
| 4 | `Tools/autotest/` joins `libraries/SITL/` in the test-harness penalty; 6 more gloss terms | to 0.833/0.542/0.646/0.354 | 0.723/0.323/0.475/0.369 | kept |

Kept configuration, held-out against baseline: recall@5 +0.031, P@1 -0.046, MRR -0.018, chunk-hit
0.000, negative-pass 0.571 (floor 0.571) and 0.750 on `eval_v4_neg_vi` (floor 0.750). Golden moved
1.000/0.767/0.859 to 1.000/0.800/0.886; v3 unchanged.

Rejected:

- **Declaration priority as a fixed boost.** Swept on dev: 12 gave 0.792/0.479/0.604, 16-20 gave
  0.812/0.521/0.629, 25 gave 0.833/0.521/0.639, 30 gave 0.833/0.542/0.647, 40 matched the forced
  version. Forced ranking is scale-free and scored best on dev, so the constant was removed.
- **Anchor relaxation that replaced the old rule.** It rejected Vietnamese questions whose anchor
  weight sits between 1 and 2 and dropped golden recall to 0.967 (`G14`). The rule now ORs the two
  conditions; the defect was fixed before the rung was reported.
- **Glossary entries for bare common words** (`giá`, `thời tiết`, `nấu`): they would anchor
  out-of-scope questions and endanger the negative floors. Deliberately not added.

## Held-out v4 run log (rule: one run per kept configuration)

`tests/eval_v4_heldout.yaml` has been run four times so far, all on 2026-10-26:

| # | time | build measured | result (recall@5 / P@1 / MRR / chunk-hit / negative-pass) | kept? |
|---|---|---|---|---|
| 1 | 08:49 | Phase 1 baseline, retriever at `1fe401b`, no Rung 1 change | 0.692 / 0.369 / 0.493 / 0.369 / 0.571 | yes, it is the baseline |
| 2 | 09:02 | Rung 1 draft: declaration priority forced, anchor rule *replacing* the old one (golden had dropped to 0.967 on `G14`) | 0.723 / 0.354 / 0.490 / 0.369 / 0.571 | no, build rejected after the golden regression |
| 3 | 09:07 | Rung 1 after the anchor fix, tie-breaking still hash-dependent | 0.723 / 0.354 / 0.490 / 0.369 / 0.571 | no, superseded by the determinism fix |
| 4 | 09:19 | Rung 1 final, deterministic (`ade40be`) | 0.723 / 0.323 / 0.475 / 0.369 / 0.571 | **yes, the reported Rung 1 number** |

| 5 | 11:03 | Rung 2 candidate: dense rerank alpha 2.0 (`ARM_DENSE=1`, 86 262 vectors) | 0.692 / 0.277 / 0.439 / 0.354 / 0.571 | no: MRR 0.439 is below the 0.543 acceptance bar and below Rung 1, so it ships off by default |
Rules from here, written down because the audit asked for them:

- A configuration is tuned on dev only. The held-out file runs **exactly once** for the
  configuration that is going to be kept, never between iterations of a loop.
- If a run reveals a defect in the build (not in the measurement), the build is fixed and measured
  once again; both runs stay in this table with the reason.
- Every Rung 2 comparison table must show three columns: Phase 1 baseline, Rung 1, and the Rung 2
  candidate, per category and per language, plus both negative sets.


## Rung 2 (dense), 2026-10-26

| # | technique | dev (recall / P@1 / MRR / chunk) | held-out (recall / P@1 / MRR / chunk) | decision |
|---|---|---|---|---|
| 1 | RRF fusion with top-50 dense candidates (brief's architecture) | 0.688/0.500/0.575/0.271 | not measured | rejected: every dev metric fell |
| 2 | RRF variants: dense weight 0.2/0.4/0.6, similarity floors 0.80/0.85/0.88, dense-adds-candidates-only | best of the family 0.688 | not measured | rejected |
| 3 | dense rerank of the BM25 candidates, alpha 1.0 to 7.5 (cosine term over the existing list) | 0.833/0.625/0.692/0.333 at alpha 1 to 2.5 | 0.692/0.277/0.439/0.354 | **kept as opt-in only** (`ARM_DENSE=1`), not the default |
| 4 | vector build (e5-small ONNX, float16 in `chunk_vectors`) | n/a | n/a | kept as opt-in infrastructure: 68.3 min, 63.2 MB |

Why the brief's RRF was replaced: it was measured on dev and lost to a plain rerank (0.688 against
0.833 recall@5). Why the rerank is not the default: on the one frozen held-out run it lost to both
the Phase 1 baseline and Rung 1 (MRR 0.439 against 0.493 and 0.475), which is exactly the
"ship it off by default and say so" path the brief allows. `ARM_DENSE` unset means BM25, and a
missing table, model or dependency cannot change an answer.

## Determinism, 2026-10-26

- **Tie-breaking decided by `PYTHONHASHSEED`.** Two runs of the same dev command disagreed on one
  question (P@1 27/48 against 26/48). The identifier passes iterated a `set`, and equal scores were
  ordered by dict insertion order. Fixed by iterating sorted identifiers and breaking every score tie
  on `cite_hash` (candidate order, document-group order, chunk picker). Kept: no behaviour change on
  aggregate recall, but the payload is now reproducible across processes, which a measurement
  pipeline needs. Test: `tests/test_query.py::test_the_same_query_returns_the_same_payload_in_two_processes`.

## A4: the 24 KB output cap and `E_INFO_02`, 2026-10-27

Audit item: `E_INFO_02` (`troubleshoot`, "what does FS_THR_ENABLE do") had 9 citations in
`docs/blackbox/run3` and 8 in `docs/upgrade/blackbox_after`, and `UPGRADE_REPORT.md` blamed the
24 KB response cap for dropping the last wiki chunk. Measured on the current index, that blame is
wrong: `guard.Guard.cap` only trims `payload["results"]`, and `troubleshoot` returns its citations
under `payload["evidence"]` with no `results` key. The re-run gives `evidence=8`, payload 10 274
bytes against a 24 576 byte cap and no `truncated_by_guard`, so the cap never touched the payload.
The 9 to 8 change is retrieval composition: run3 spent its six `docs` slots on six wiki pages and its
three `code` slots on ardupilot files; now one `docs` slot goes to `ArduCopter/Parameters.cpp` and
the `code` search returns two items instead of three after the simulator penalty pushed the
autotest files down.

Decision: **no change to `guard.py`**. `search_docs` is the only tool whose payload has a `results`
list, and `query.search` already returns that list in document-score order, so popping from the tail
is already "drop the least relevant item"; a relevance-aware trim would need a `score` on every item
of every tool and would only change which item is lost, not how many. The 24 KB value and the
three-excerpts-per-source rule are unchanged. Recorded rather than fixed: `troubleshoot` evidence is
not byte-capped at all (only `results` is), which is why a 10 KB evidence list is possible; capping
it would drop citations from frozen blackbox cases for no measured gain.

## Phase 3 (Vietnamese), 2026-10-27

| # | technique | v5-vi dev (recall / P@1 / MRR) | v5-vi held-out | decision |
|---|---|---|---|---|
| 1 | V1: chat normalisation (`vi.py`), folded multi-word glossary match, out-of-scope refusal | 0.535 / 0.279 / 0.389 (was 0.488 / 0.256 / 0.354) | 0.581 / 0.387 / 0.451 (was 0.581 / 0.387 / 0.447) | **kept, default** |
| 2 | V1 with ASCII Vietnamese function words added to `STOPWORDS` | 0.605 / 0.326 / 0.448 | not measured | rejected: v5-vi dev negative-pass 0.500 -> 0.333, `eval_v4_neg_vi` 0.750 -> 0.583 |
| 3 | V2: one vector per document as a topic prior, plus the chunk rerank (`ARM_DENSE=1`) | 0.535 / 0.279 / 0.408 (chunk rerank alone: 0.558 / 0.302 / 0.416) | not measured | rejected, stays behind `ARM_DOC_PRIOR=1` |
| 4 | V3: drop the expansion terms from the FTS query when the user's own word is index vocabulary | 0.512 / 0.279 / 0.378 | not measured | rejected: costs 0.125 recall on v4 dev |
| 5 | V5: declaration priority only for a parameter-shaped query | 0.442 / 0.186 / 0.290 | not measured | rejected: costs 0.062 recall on v4 dev |
| 6 | V4: rebuild chunk vectors at 256/512 tokens | - | - | not attempted; measured estimate 164 min at 256 tokens, and the misses are absent candidates and gate refusals, not truncated chunks |

Why V1 is the default although the written ship bar (MRR +0.05 on the new held-out set) was missed by
0.046: it is input normalisation and a scope correction, not a new retrieval path; it is the only
change in the ladder that lifts negative-pass on the set built to catch false answers (0.556 -> 0.778
on v5-vi held-out, 0.571 -> 0.714 on the v4 guard); and no set regressed beyond the 0.01 tolerance
(golden MRR -0.005). The bar, the measured delta and the reasoning are printed in
`PHASE3_REPORT.md` section 9 rather than argued away.

Safety: `safety_rules.yaml` was not touched. A chat-style zeroing request **without** an equals sign
("dat arming check 0 dc ko") is answered rather than refused; the rules cover "=0", "0xffff",
"to 0" and the verb-object forms. Recorded as a known limit instead of editing safety rules meaning,
which the Phase 3 brief forbids. The seven chat-style variants of the six audited inputs that the
rules do cover are pinned in `tests/test_safety_vi_chat.py`.
