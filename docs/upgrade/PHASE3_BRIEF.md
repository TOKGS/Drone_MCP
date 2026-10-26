# PHASE 3 BRIEF: cleanup, then close the Vietnamese gap

> Tóm tắt tiếng Việt: Phase 1-2 đã merge vào `master` (commit `235b36b`). Phase 3 gồm **Phần A** (sửa lỗi
> vặt tìm thấy khi audit) và **Phần B** (mở rộng: thu hẹp khoảng cách tiếng Việt so với tiếng Anh, đo bằng
> bộ đánh giá tiếng Việt MỚI, vì held-out v4 đã dùng 6 lần). Luật cứng, cách dùng subagent và cách báo cáo
> vẫn như `DEEPSEEK_BRIEF.md` (phần 2, 3, 6). File này chỉ ghi phần khác.

Read first: `CLAUDE.md`, `docs/upgrade/DEEPSEEK_BRIEF.md` (sections 2, 3, 6, 11 still apply in full),
`docs/upgrade/UPGRADE_REPORT.md`, `docs/upgrade/DECISIONS.md`, `docs/upgrade/rung1.md`, `docs/upgrade/rung2.md`.

Work on a **new branch from `master`**: `feat/phase3-vi-retrieval`. Same rules: small commits, no push, no force,
no `--no-verify`, never edit frozen files, never commit `data/` or models.
Progress file: `docs/upgrade/PROGRESS3.md` (new; the old `PROGRESS.md` is history, do not edit it).
Final report: `docs/upgrade/PHASE3_REPORT.md`.

---

## 0. State you start from (verify, do not assume)

```powershell
git checkout master; git log --oneline -1           # 235b36b Merge feat/eval-v4-hybrid-retrieval ...
python -m pytest -q                                  # 184 passed, 1 skipped
python -m research.eval_retrieval --set tests/eval_v4_heldout.yaml --aggregate-only --no-floor
#  recall@5 0.723  P@1 0.323  MRR 0.475  chunk-hit 0.369  negative-pass 0.571
python -m research.eval_retrieval --set tests/eval_v4_neg_vi.yaml --aggregate-only --no-floor    # 0.750
python scripts\bench.py                              # p95 under 400 ms (about 180-240 ms on a quiet machine)
```

Where the retriever is weak (held-out v4, default build): **Vietnamese recall@5 0.516, MRR 0.256**, English 0.906 / 0.678.
Rung 1 moved Vietnamese recall +0.064 but its MRR fell. The chunk-level dense rerank (opt-in) did not help.
Categories that lost MRR after Rung 1 on held-out: troubleshoot -0.267 (n=5), elrs_edgetx -0.167 (n=6), wiki -0.128 (n=13).

**Evidence budget.** `tests/eval_v4_heldout.yaml` has been run 6 times. It is now a **regression guard only**: run it at most
**once per kept configuration**, report it, never use it to choose between options. Choices are made on dev sets. The new
Vietnamese held-out set (Part B) is the one that judges Phase 3.

---

## PART A: cleanup (do this first, one commit each)

| ID | Problem found in the audit | Fix | Done when |
|---|---|---|---|
| A1 | `README.md:676` and `README.vi.md:660` ("Status" section) still say "141 tests"; everything else says 184. `check_readmes.py` did not catch it. | Update the numbers, **and** make `scripts/check_readmes.py` fail when any "N tests / N passed" number in either README differs from the real collected count (`pytest --collect-only -q`, minus the documented skips) or from the other README. Add a unit test for the checker with a planted wrong number. | the checker fails on a planted `141` and passes on the repo |
| A2 | `UPGRADE_REPORT.md` says "19 mutation mutants" in section 1 but 18 in section 5. | Correct to the true number (18 scored plus 1 equivalent) with the raw line. Do not rewrite history elsewhere. | one consistent number |
| A3 | Mutant `M15` (text identifier boost) survives. | Either add a test that kills it, or prove it equivalent and flag it `equivalent` in `research/mutation.py` with the reasoning in `docs/mutation-report.md`. Do **not** claim a score you did not run. | `mutation_check.py` output pasted; score reported honestly |
| A4 | `E_INFO_02` lost its 9th citation because `Parameters.cpp` took the first slot and the 24 KB cap trimmed the last wiki chunk. | Investigate whether the cap should drop the *least relevant* item rather than the last. If you change `guard.py` ordering, keep the cap value and the 3-excerpts-per-source rule. Add a test. If you decide not to change it, record why in `DECISIONS.md`. | decision recorded; blackbox E_INFO_* still has no regression |
| A5 | The dense experiment index lives at `data/exp/index.sqlite`; its path is undocumented outside the reports. | Add a short "experiment index" paragraph to `docs/upgrade/rung2.md` or `CLAUDE.md`: how to build it, how to point at it (`ARM_DATA_DIR`, `ARM_MODEL_DIR`). | the paragraph exists |
| A6 | Held-out v4 is spent. | Add a note at the top of `docs/eval-v4.md`: the file is a regression guard from now on, 6 runs so far (link `DECISIONS.md`). | the note exists |

Part A gate: `pytest -q`, `check_readmes.py`, `check_traceability.py`, `fidelity_scan.py`, `audit_safety` all green. Update `PROGRESS3.md`.

---

## PART B: close the Vietnamese gap

### B0. A fresh ruler: eval set v5-vi  (do before touching the retriever)

Same protocol as Phase 1, with these differences:

- **Language:** at least **110 questions**, all Vietnamese or Vietnamese-English mixed. Of these, at least **40 % written without diacritics**, and
  several in "chat style" (abbreviations, missing punctuation, mixed English identifiers, typos a real user makes).
- **Categories** (same eight as v4): param 20, code 20, protocol 15, hwdef 10, wiki 20, elrs_edgetx 10, troubleshoot 10, negative >= 15.
  Negatives must be genuinely out of scope but **technical-sounding** (PX4, Betaflight, INAV, Mission Planner scripting questions about other products, unpinned
  ArduPilot 3.x behaviour) as well as everyday topics, because the dangerous failure for retrieval changes is a false answer to those.
- **Independence:** writers are fresh subagents that never read `query.py`, `glossary.vi-en.yaml`, the v4 files, or any eval run output. They pick a passage from
  `data/corpus/` or via read-only SQL, then write the question. Questions must not be paraphrases of any v4 question (the validator checks normalised overlap
  against all v4 files and rejects >= 60 % token overlap).
- **Splits:** `tests/eval_v5_vi_dev.yaml` (~40 %, tunable) and `tests/eval_v5_vi_heldout.yaml` (~60 %, frozen with `docs/eval-v5-vi-heldout.sha256` and a dev sha file).
  Stratify by (category, lang). The merge script prints counts and hashes only, never question text. After the freeze **nobody opens the held-out file**.
- **Reuse `research/validate_eval_set.py --strict-v4`** (path matching is case-sensitive since the Phase 1 errata) and extend it for the cross-set overlap check.
  Extend `research/make_eval_v4.py` or add `make_eval_v5.py`; keep the old one working.
- **Baseline first:** run the *default* build and the *opt-in dense* build on both v5 splits and save JSON under `docs/upgrade/baseline3/`.

Exit criteria for B0: counts met, validator `errors: 0`, hashes committed, evaluator refuses a tampered file (reuse the existing test pattern), baselines saved,
`docs/eval-v5-vi.md` written (protocol, counts, baseline tables, limits).

### B1. Ablation ladder for Vietnamese  (each rung: measure on v5-vi **dev**, keep or revert, one commit)

Order by cost. Stop a rung early if it clearly does not help.

**V1: data-driven glossary and normalisation (cheap, no new dependencies).**
- Normalise Vietnamese input once: Unicode NFC/NFD, strip diacritics for matching, collapse repeated letters and common chat abbreviations
  ("k"/"ko" for "không", "dc"/"đc" for "được", "ntn" for "như thế nào", "j" for "gì"). Keep the original for display.
- Mine candidate vi to en pairs from the corpus itself offline (for example Vietnamese wiki-style terms against English headings and parameter display names in `params`),
  review them, and add the useful ones to `glossary.vi-en.yaml`. Only phrases, never bare common words. Every entry justified by a *class* of questions, not a question.
- Test: add unit tests for the normaliser; keep determinism (two-process test) green.

**V2: document-level semantic matching (cheap embeddings).**
- Embed **one vector per document** from `path words + title + heading_path list` (about 7 400 documents, 128 tokens is plenty) with the same e5-small ONNX model.
  Build time should be minutes, not hours; log the measured time. Store in a new table `doc_vectors` in the index (float16), resumable, optional like `chunk_vectors`.
- Use it as a *candidate generator and prior*, not a reranker of chunks: top documents by cosine contribute to the document score before chunk selection.
  Gate it behind the same `ARM_DENSE=1` opt-in first.
- Keep the anchor gate in front: a query the gate rejects must not reach this stage.

**V3: query-side translation by expansion (still offline).**
- If the glossary fires, add the English expansion as additional FTS terms (already done) **and** weight expansion terms below original English identifiers.
  Evaluate per-term weighting only if V1/V2 leave a measurable gap.

**V4 (optional, only if V2 shows promise): full chunk embedding at 256 or 512 tokens.** Previous build truncated at 128 tokens. Estimate wall time first
(measured: 128 tokens = 21 chunks/s; 256 tokens was 8.8 chunks/s = about 164 min). Run in the background, resumable, on a **copy** of the index. Only attempt
if you can finish and measure it; otherwise record "not attempted" with the estimate.

**V5: recover the Rung 1 regression** on `elrs_edgetx`, `troubleshoot`, `wiki` rank-1 precision. Investigate on **v5-vi dev and v4 dev only** (never on a held-out
file) why Rung 1 moved declarations or glossary hits above the right page; fix with a general rule (for example: declaration priority only when the query is
clearly parameter-shaped), not a per-question hack.

### B2. Keep/ship rules

- A technique is kept only if it improves **v5-vi dev** MRR and does not reduce `negative-pass` on `eval_v4_dev`, `eval_v4_neg_vi`, or the v5 dev negatives.
- The final configuration is run **once** on `eval_v5_vi_heldout` and **once** on `eval_v4_heldout` (guard) and `eval_v4_neg_vi`.
- **Ship as default** only if on v5-vi held-out: MRR improves by >= 0.05 absolute over the default baseline and recall@5 does not drop, no category loses more than
  0.05 recall@5 (state sample sizes; categories with n < 8 are reported but flagged "low n"), and on v4 held-out: recall@5 does not drop below 0.70, MRR below 0.45,
  negative-pass below 0.571, and neg-vi below 0.750. Otherwise keep it behind a flag and say so in the report. A negative result is acceptable; hiding it is not.
- Everything in `DEEPSEEK_BRIEF.md` section 8 gates must still pass (pytest, fidelity, param citations, verify_citations, audit_safety, bench, mutation, blackbox
  with 0 regressions vs `docs/upgrade/blackbox_after`, offline test, safety with dense on and off, dense-absent fallback).
- Safety is unchanged: no edits to `safety_rules.yaml` meaning. Add Vietnamese chat-style variants (no diacritics, abbreviations) of the existing six safety inputs
  to a **new** test file and confirm they are still refused or answered correctly; if the normaliser makes any of them slip through, that is a defect to fix before shipping.

---

## Operational notes (lessons from earlier rounds)

- Write files with LF. Never rewrite a file in text mode on Windows; read and write bytes or use `newline="\n"`. Check `wc -c` and `git diff --stat` after writing
  `PROGRESS3.md`, `query.py`, YAML sets. (This corrupted `PROGRESS.md` twice.)
- Do not print question text from any frozen held-out set, in logs, JSON, error messages or the report. Counts, ids and aggregate tables only.
- `ARM_DENSE=1` with `ARM_DATA_DIR` pointing at the experiment folder also needs `ARM_MODEL_DIR`; otherwise the dense path warns and falls back.
- Rate guard is 60 calls/min per process in production; tests reset it. Long eval loops go through `research.eval_retrieval`, which already handles it.
- Latency budget is p95 <= 400 ms warm for `search_docs`; report the cold start separately. If the machine is loaded, re-measure when quiet and say which run is which.
- Subagents: one owner per file, one worktree each, long jobs in the background with a log, verify their claims by re-running the command yourself.

## Work packages

| WP | Does | Files it may edit |
|---|---|---|
| A | Part A items | `scripts/check_readmes.py`, `README*.md`, `docs/upgrade/UPGRADE_REPORT.md`, `research/mutation.py`, tests, `docs/*` notes, possibly `guard.py` |
| B0-tools | v5 merge/validate/overlap check | `research/make_eval_v5.py`, `research/validate_eval_set.py`, tests |
| B0-writers (x3, parallel) | question fragments | `docs/upgrade/scratch/q5_*.yaml` only |
| V1 | normaliser + glossary | `src/ardupilot_research_mcp/query.py` (normalisation hook) or a new `vi.py`, `glossary.vi-en.yaml`, tests |
| V2 | doc vectors build + prior | `research/build_vectors.py` (add a `--docs` mode) or `research/build_doc_vectors.py`, `dense.py`, `db.py` (table only), `query.py` (after V1 merges) |
| V4/V5 | optional rebuild, regression recovery | same as above, after V2 |
| Docs | README/CLAUDE.md/eval docs/report | docs only, last |

`query.py` is shared by V1, V2, V5: merge in that order, one at a time.

## Deliverable: `docs/upgrade/PHASE3_REPORT.md`

Sections: 1 Summary; 2 Part A (each item with the commit and the raw command output); 3 v5-vi evidence (counts, validator, hashes, baselines);
4 Ladder table (one row per rung/config: dev and held-out recall@5 / P@1 / MRR / chunk-hit / negative-pass, delta, p95, decision); 5 Per-category and per-language
deltas (`--compare` output) for v5-vi **and** v4 guard; 6 Gate results (raw); 7 Decisions and rejected ideas; 8 Costs (index size, build time, cold start, new
dependencies and licenses); 9 Deviations from this brief; 10 Known limits and unverified claims; 11 Reproduce; 12 Commit list.

Finish with: `PROGRESS3.md` fully ticked, branch committed, `git status` clean, then report **"READY FOR AUDIT PHASE 3"** with the branch name.
Stop and write to BLOCKERS instead of guessing if: a frozen file would need editing, a baseline differs, a license is unclear, a gate regresses without explanation.
