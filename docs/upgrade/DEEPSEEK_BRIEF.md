# DEEPSEEK BRIEF: Eval set v4, then hybrid retrieval

> Tóm tắt tiếng Việt cho chủ dự án: file này giao cho agent DeepSeek làm hai việc theo thứ tự.
> **Phase 1**: dựng bộ câu hỏi đánh giá lớn (>= 120 câu, chia dev / held-out, đóng băng bằng hash).
> **Phase 2**: nâng retrieval (cải tiến từ khóa, rồi hybrid BM25 + embedding chạy offline) và chứng minh
> bằng số đo trên bộ held-out. Agent được phép dùng subagent, phải ghi tiến độ vào
> `docs/upgrade/PROGRESS.md`, và nộp `docs/upgrade/UPGRADE_REPORT.md` để Claude audit.

You are an engineer taking over work on `ardupilot-research-mcp`. Read this whole file before touching
anything. It is written to be followed top to bottom. Where a choice is yours, the file says so.

---

## 0. TL;DR

| | |
|---|---|
| Repo | `D:\Skill_tulan\ardupilot-research-mcp` (own `.git`, branch `master`). Read `CLAUDE.md` first, then `README.md`. |
| Product | Local, offline, read-only MCP server. Answers ArduPilot / ELRS / EdgeTX / CRSF / MAVLink questions from a pinned corpus and returns citations. |
| Your job | Phase 1: build eval set v4. Phase 2: improve retrieval and prove it with that set. |
| Output | Code + tests + `docs/upgrade/PROGRESS.md` (live) + `docs/upgrade/UPGRADE_REPORT.md` (final). |
| Auditor | Claude will re-run your commands and check every claim. Anything not backed by raw command output counts as unverified. |
| Shell | Windows 10, PowerShell. Python 3.11. Use `python -m ...`. |

Baseline you must reproduce before changing anything:

```powershell
cd D:\Skill_tulan\ardupilot-research-mcp
python -m pytest -q                       # expect: 145 passed, 1 skipped  (README says 141, it is stale)
python -m research.eval_retrieval --set tests/golden.yaml --aggregate-only        # recall@5 1.000 P@1 0.767 MRR 0.859
python -m research.eval_retrieval --set tests/heldout_v3.yaml --aggregate-only    # recall@5 0.933 P@1 0.833 MRR 0.868
python scripts\bench.py                   # search p50 ~58 ms, p95 ~186-339 ms, budget 400 ms
```

If any baseline number differs, stop and record the difference in `PROGRESS.md` before continuing.

---

## 1. Context map (what exists, so you do not rediscover it)

```
src/ardupilot_research_mcp/
  query.py          search(con, query, scope, version, tier_max, limit) -> dict   <- the retrieval code
  db.py             schema: sources, documents, chunks(text, distilled, heading_path, line_start/end, cite_hash),
                    chunks_fts (FTS5, external content over chunks.distilled), params, mavlink_msgs, mavlink_enums
  cite.py           cite_id + 600-char excerpt + pinned URL (do not change the contract)
  safety.py         refuse/inform gate for troubleshoot (do not weaken)
  tools/_base.py    guarded()/guarded_pure() wrappers, LIMITS, rate guard (60/min), 24 KB response cap
research/
  eval_retrieval.py   metrics: recall@5, P@1, MRR over a YAML set
  make_heldout_v3.py  how v3 was generated (blind, fixed seed, prints counts + sha only)
  build_all.py        build pipeline, one subprocess per stage
  build_params.py / build_mavlink.py / extract.py / fetch.py
tests/
  golden.yaml         30 questions, tunable dev set
  heldout_v3.yaml     30 questions, frozen, sha in docs/heldout-v3.sha256
  heldout_locked.yaml / heldout_v2.yaml   burned, do not use for scoring
  blackbox_cases.md   108 frozen tool-level cases (never edit)
data/index.sqlite   182 MB, 86 262 chunks, built. data/corpus = extracted source files. Both gitignored.
```

How `search()` works today (read `query.py` lines 99-376 yourself before changing it):
fold + Vietnamese glossary expansion per token -> stopwords -> **anchor gate** (content words must exist in
the corpus, else `found:false`) -> FTS5 BM25 candidates (top `max(limit*6, 24)`) + a literal-identifier
`LIKE` pass -> per-document best chunk with boosts (path tokens, heading tokens) and a penalty for
`libraries/SITL/` -> `_boundary_hits` / `_heading_extra` chunk picker -> scope notes + confidence.

Eval YAML format (keep it; extend it only additively):

```yaml
- id: V4-D-001
  lang: vi                   # vi | en | mixed
  q: "..."
  scope: all                 # optional, default all
  expect:                    # a result is a hit if source_id matches AND path contains `path`
    - { source: ardupilot_wiki, path: "common-cuav-p9" }
```

`research/eval_retrieval.py` currently does **not** verify set hashes (README claims it does; that claim is
false today). Fixing that is task P1-A.

Known weak spots to keep in mind, **not** to tune against individually: frozen blackbox cases `C4`
("where does ArduPilot parse CRSF"), `C10` ("SERIAL port protocol RC input"), `C11` ("EdgeTX CRSF
telemetry"); the right file is indexed but misses the top 5.

---

## 2. Hard rules (violating any of these fails the audit)

1. **No fabricated numbers.** Every metric in the report must be pasted from a command you ran, with the command.
2. **Never edit frozen files**: `tests/heldout_locked.yaml`, `tests/heldout_v2.yaml`, `tests/heldout_v3.yaml`,
   `tests/blackbox_cases.md`, `docs/heldout*.sha256`. Never edit the v4 held-out file after it is frozen.
3. **No tuning on held-out data.** Held-out v4 is read by the evaluator only, with `--aggregate-only`.
   No human or agent opens it or prints its misses after the freeze (section 4, step P1-E). Tune only on `golden.yaml` and v4-dev.
4. **Offline at answer time.** `query.py`, `tools/`, `server.py` must not import network modules. Only
   `src/ardupilot_research_mcp/ingest/` and `research/` may reach the network. `tests/test_offline.py` enforces this: read it.
5. **Citations stay byte-verbatim.** Do not modify `chunks.text`. `scripts/fidelity_scan.py` must still say 0 mismatch.
6. **Safety gate is untouchable in meaning.** Do not edit `safety_rules.yaml` semantics or weaken `safety.py`.
   New retrieval paths must still pass through the same citation filter (`dangerous_excerpt`). `python -m research.audit_safety` and
   `tests/test_safety*.py` must stay green.
7. **Out-of-scope questions still return `found:false`.** A dense retriever always returns nearest neighbours; it must never bypass the anchor gate.
8. **Git hygiene.** Work on branch `feat/eval-v4-hybrid-retrieval`. Small commits with clear messages. Do not push, do not force, do not
   `--no-verify`, do not commit `data/`, models, or `research/cache/`.
9. **Do not delete** `data/index.sqlite` or `data/corpus`. Experiments run on a **copy** (section 6).
10. **Stop and write to `PROGRESS.md` under "BLOCKERS"** instead of guessing when: a baseline differs, a frozen file would need editing, a
    dependency has a license you cannot confirm, or a gate regresses and you cannot explain why.

---

## 3. How to work: subagents, branches, progress file

You may (and for the long tasks should) use subagents. Rules so they do not collide:

- **You are the orchestrator.** You decide the plan, hand each subagent one work package (WP) from this file, collect and verify its output.
  A subagent's claim is not evidence until you re-run its command yourself.
- **One owner per file.** The ownership table in section 7 says which WP may edit which files. Two subagents never edit the same file.
- **Isolation.** Each code-writing subagent works in its own git worktree under `D:\Skill_tulan\wt\<wp-name>` created from the feature
  branch. Do **not** copy the 190 MB index into each worktree; point at the shared read-only one with
  `$env:ARM_DATA_DIR = "D:\Skill_tulan\ardupilot-research-mcp\data"`. (Only WP-H builds a modified index; it uses its own copy.)
- **Long jobs** (embedding 86k chunks, full gate runs, blackbox reruns) go in the background with output to a log file; poll the log, do not wait blind.
- **Progress file**: create `docs/upgrade/PROGRESS.md` first, with one checkbox per task id below. After every finished task, update it with:
  status, commit hash, the command you ran, and the key line of its output. If your context is reset, this file is how you resume.

`PROGRESS.md` skeleton:

```markdown
# Progress
## Baseline (copied raw output)
## Tasks
- [ ] P1-A evaluator upgrade        owner:      commit:      evidence:
- [ ] P1-B question writers         ...
## Decisions (what you chose and why, one line each)
## BLOCKERS
```

---

## 4. PHASE 1: Eval set v4

**Goal:** a trustworthy ruler. At least **120 questions**, stratified, with ground truth chosen from the *corpus*, not from what the
current retriever returns, split into a tunable dev file and a frozen held-out file.

**Why it matters:** v3 has 30 questions; one question is 3.3 points of recall. Phase 2 cannot be judged on that. Also the v3 questions are
template-generated from headings ("Where is X documented?"); v4 must contain real user-style questions.

### P1-A. Evaluator upgrade  (owner: WP-A; files: `research/eval_retrieval.py`, `tests/test_eval_retrieval.py` new)

Extend, keep old behaviour and old CLI working (golden and v3 must give the same numbers as the baseline):

1. `--verify-sha docs/<file>.sha256` or automatic: if a `docs/<setname>.sha256` exists for the set, compare SHA-256 and **exit non-zero on mismatch**.
   Apply this to v3 and v4-heldout. (This makes the README claim true.)
2. New optional fields per question, all additive:
   - `category`: one of `param`, `code`, `protocol`, `hwdef`, `wiki`, `elrs_edgetx`, `troubleshoot`, `negative`.
   - `answer_snippet`: a verbatim substring (>= 12 chars) that the correct citation excerpt should contain.
   - `expect_none: true`: question is deliberately out of scope; pass iff the payload has `found:false` or zero results.
3. New metrics, printed overall **and per `category` and per `lang`**: recall@5, P@1, MRR, **chunk-hit@5** (a result in the top 5 is a hit AND its excerpt
   contains `answer_snippet`, only counted for questions that have one), **negative-pass-rate** (for `expect_none`).
   Negatives are excluded from recall/P@1/MRR.
4. `--json out.json` writes machine-readable results; `--compare base.json new.json` prints a per-category delta table and flags any
   category whose recall@5 or MRR drops.
5. `--aggregate-only` must print **no question text and no miss list**, only the aggregate and per-category tables (category counts are fine).
6. Unit tests with a tiny fake DB/set: hash mismatch fails, negative scoring, chunk-hit scoring.

Done when: golden and v3 reproduce baseline numbers exactly; `pytest` green.

### P1-B. Question writing  (owner: 3 parallel subagents WP-B1, B2, B3; files: only their own scratch file)

Each writer produces a YAML fragment at `docs/upgrade/scratch/q_<name>.yaml` (this folder is deleted/ignored after merge; add to `.gitignore`).

Writers must follow **all** of these:

- **Ground truth from the corpus.** Open files under `data/corpus/<source>/...` (or query the `documents`/`chunks` tables directly with SQL), pick a
  passage, then write a question a real user would ask whose answer is in that passage. Record the file in `expect` and a verbatim `answer_snippet` from it.
- **Writers must not call `query.search`, `search_docs`, or any retrieval code, and must not read `query.py`.** The point is that questions are
  independent of how the retriever behaves. SQL over `documents`/`chunks` for *browsing* is allowed.
- **Defensible ground truth.** If the answer legitimately exists in 2-3 files, list them all in `expect`. Do not pick questions whose answer is a generic heading
  ("Overview", "Parameters") shared by many files.
- **Real phrasing, not templates.** Mix: short keyword queries ("ARMING_SKIPCHK là gì"), full sentences, symptom descriptions ("drone không arm được báo PreArm RC not
  calibrated"), identifier-only queries (`AP_RCProtocol_CRSF`), and "how do I" questions.
- **Language mix across the whole set:** >= 40 % Vietnamese; of those, a third written **without diacritics** ("tat failsafe", "toc do bay") and some mixed Vietnamese-English
  ("set param RC_OPTIONS de bat 420kbaud ELRS"). The rest English.
- **Do not write questions that ask the server to do something dangerous** (disable failsafe etc.); those are covered by the safety suites, not here.

Target counts (minimum, after merge). Split writers by category group:

| Writer | Categories | Count |
|---|---|---|
| WP-B1 | `param` 20, `hwdef` 10, `protocol` 15 | 45 |
| WP-B2 | `code` 20, `wiki` 20, `elrs_edgetx` 10 | 50 |
| WP-B3 | `troubleshoot` 10, `negative` 12 (out of scope: PX4, Betaflight tuning, stock prices, cooking, unpinned versions like "ArduPilot 3.2", etc.) , plus 8 extra Vietnamese-no-diacritics variants of questions from other writers' categories | 30 |

Total >= 125. Negatives use `expect_none: true` and `category: negative`; no `expect`.

Give every writer: this section, the YAML format, the corpus layout (`data/corpus/<source_id>/`), the source ids (`ardupilot`, `ardupilot_wiki`, `mavlink`,
`expresslrs`, `expresslrs_docs`, `edgetx`, `crsf_spec`), and a unique id prefix (`V4-B1-`, `V4-B2-`, `V4-B3-`).

### P1-C. Validation script  (owner: WP-A; file: `research/validate_eval_set.py` new)

A script that, for a fragment or merged set, checks and **prints only counts and error ids, never question text**:

- schema valid, ids unique, `lang` in {vi,en,mixed}, `category` known;
- every `expect.path` matches >= 1 row in `documents` for that `source`;
- every `answer_snippet` occurs verbatim in at least one chunk of a matching document;
- no duplicate questions (normalised), no question that is a substring of another;
- `expect_none` questions are not trivially answerable: reject if the question has >= 3 content words that each appear in >= 3 documents (it is not really out of scope).

Writers run it on their fragment and fix errors before handing back.

### P1-D. Merge and split  (owner: WP-A, run by you)

`research/make_eval_v4.py` (new) merges fragments, then splits **stratified by category and lang** with a fixed seed:

- `tests/eval_v4_dev.yaml`: ~40 %, tunable, treated like `golden.yaml`.
- `tests/eval_v4_heldout.yaml`: ~60 %, frozen.

The script prints only counts per (category, lang, split) and the SHA-256 of each file. **It must not print any question.**

### P1-E. Freeze  (you)

1. Run `validate_eval_set.py` on both files; fix errors **in the scratch fragments and re-merge** (only before freezing).
2. Write `docs/eval-v4-heldout.sha256` (`<sha>  tests/eval_v4_heldout.yaml`) and `docs/eval-v4-dev.sha256`. Commit.
3. From this point nobody opens `tests/eval_v4_heldout.yaml` as text. The evaluator reads it; you read aggregates only.
   Add a one-line note in the file header comment and in `docs/eval-v4.md`.
4. Delete `docs/upgrade/scratch/` contents from the working tree (keep them out of git).

### P1-F. Baseline  (you)

On the **untouched** retriever, run and save raw output to `docs/upgrade/baseline/`:

```powershell
python -m research.eval_retrieval --set tests/eval_v4_dev.yaml     --json docs/upgrade/baseline/dev.json
python -m research.eval_retrieval --set tests/eval_v4_heldout.yaml --aggregate-only --json docs/upgrade/baseline/heldout.json
python -m research.eval_retrieval --set tests/golden.yaml          --json docs/upgrade/baseline/golden.json
python -m research.eval_retrieval --set tests/heldout_v3.yaml --aggregate-only --json docs/upgrade/baseline/v3.json
```

Write `docs/eval-v4.md`: protocol, category/lang counts, baseline tables, known limits. Write it in the style of `docs/eval-heldout-v3.md`.
Add the new sets to `.github/workflows/ci.yml` only as **non-blocking** report steps in the weekly job (they need the index).

**Phase 1 exit criteria** (all must hold, include the evidence in the report):

- [ ] >= 120 questions total, >= 40 % vi, all 8 categories present, >= 10 negatives, >= 60 with `answer_snippet`.
- [ ] validator passes with 0 errors on both files.
- [ ] two sha256 files committed; evaluator exits non-zero if either file is altered (prove it with a test, not by editing the real file).
- [ ] baseline JSONs saved; `docs/eval-v4.md` written.
- [ ] `pytest -q` green, `scripts/check_readmes.py` and `scripts/check_traceability.py` green.

Stop here, commit, update `PROGRESS.md`. Then Phase 2.

---

## 5. PHASE 2: Retrieval upgrade

**Goal:** better ranking on real user phrasing, especially Vietnamese and identifier-vs-prose confusion, without breaking anything else. **Honest outcome
is allowed**: if a technique does not help on held-out v4, say so and do not ship it as default.

Work as an **ablation ladder**. Each rung is measured alone against the previous one, on dev (tune) and held-out (report), then kept or reverted.

### Rung 0: baseline (done in P1-F)

### Rung 1: cheap lexical improvements  (owner: WP-C; files: `src/ardupilot_research_mcp/query.py`, `glossary.vi-en.yaml`, `tests/test_query*.py`)

Candidates (try, measure, keep only what helps; each as its own commit so it can be reverted):

1. **Glossary growth, data-driven.** From the v4-**dev** failures only, add general Vietnamese/diacritic-free terms to `glossary.vi-en.yaml`. Matching stays per
   token. No question-specific entries (a glossary line must be useful to a class of questions; justify each in a commit message).
2. **Field-aware scoring.** Weight matches in `path` and `heading_path` separately from body; weight whole-word identifier matches higher than substring.
3. **Document-level prior.** Prefer docs whose *title/path* matches the query for "what is X / where is X" style questions; prefer code files for identifier-only queries.
4. **Query-type routing.** Cheap classifier (regex, no ML): identifier-only, param-like (`^[A-Z][A-Z0-9_]+$`), symptom/sentence, how-to. Different boost weights per type.
5. **Proximity / phrase boost** (FTS5 `NEAR` or post-filter) for multi-word queries.

Constraint: p95 latency from `scripts\bench.py` stays <= 400 ms.

### Rung 2: dense retrieval + fusion  (owners: WP-D build side, WP-E query side)

Add an **optional** semantic retriever that runs offline at answer time, fused with BM25. Architecture (follow it unless you have measured evidence for a change, and then log the decision):

```
build time (network allowed, ingest/ or research/ only)        answer time (offline)
  download model once -> data/models/<name>/  (gitignored)      query -> encode (onnxruntime, CPU)
  embed every chunks.distilled (or text) -> vectors               -> cosine vs all vectors (numpy matmul)
  store in index.sqlite table chunk_vectors(rowid, dim, blob)     -> top-N dense candidates
                                                                  -> fuse with BM25 top-N by RRF (k=60)
                                                                  -> existing per-document scoring + picker
                                                                  -> anchor gate still decides found:false
```

Requirements:

- **Model choice is yours but must satisfy:** multilingual including Vietnamese; ONNX-runnable on CPU; permissive license you have *read in the model's own
  license file* (record it in `docs/license-notes.md`); small enough for a laptop (<= ~500 MB on disk). A strong default candidate to evaluate first:
  `intfloat/multilingual-e5-small` (384-d). Also try one alternative so the choice is evidence-based (for example `paraphrase-multilingual-MiniLM-L12-v2`
  or `BAAI/bge-m3` if the size is acceptable). Remember e5 models need the `query: ` / `passage: ` prefixes.
- **Do not use `torch` at answer time.** onnxruntime + numpy + a tokenizer only. This machine has torch installed; do not depend on it.
- **Optional dependency.** Put them in `pyproject.toml` under `[project.optional-dependencies] embeddings = [...]` with exact lower bounds. The base install and
  fresh-clone CI (no index, no model) must still pass. If the extras, the model, or the `chunk_vectors` table are absent, `search()` silently falls back to BM25 and
  `index_status` reports `dense: absent`. Add tests for the fallback path.
- **Store vectors in `index.sqlite`** (float16 or int8-quantised to keep the file reasonable; report the size cost). Single-file answer-time contract stays true.
- **Build stage:** `research/build_vectors.py` + a stage in `research/build_all.py`. Resumable by `cite_hash`, progress logged, runs in the background. Estimate and log
  the wall time on a small batch before launching the full run (86 262 chunks). Truncate long chunks to the model's max length and say so.
- **Lazy model load** at first query, not at server start, so `tools/list` and non-search tools stay instant. Log load time. Cache the loaded session in-process.
- **Fusion details:** candidates from BM25 (existing) and dense (top 50); RRF with k=60 as the starting point; then the *existing* per-document scoring, boosts, SITL
  penalty, picker, scope notes. Tune the fusion weight and N on **dev**; report held-out once per configuration you decide to keep.
- **Anchor gate order:** gate first. If the gate says out of scope, return `found:false` before any dense lookup. Additionally evaluate whether a dense
  similarity floor reduces false positives on negatives; keep it only if the negative-pass-rate does not fall.
- **Determinism:** same query twice gives byte-identical payloads (sort ties by `cite_hash`). `numpy` matmul in float32 is fine; document how you quantise.
- **Safety:** dense candidates go through exactly the same citation/excerpt filtering as BM25 ones. Add a test that a dangerous-recipe chunk reached only via
  the dense path is still filtered.
- **Latency budget:** `scripts\bench.py` p95 <= 400 ms warm with dense enabled; report cold first-query time separately.

### Rung 3 (optional, only if Rung 2 helps and time remains): rerank top-20 by a cross-encoder or by chunk-level features. Same measure-and-keep rule. Skip if unsure.

### Hard-negative check

After Rung 2, run the safety and offline suites with dense enabled **and** with it absent. Both must pass.

---

## 6. Experiment hygiene (important for a fair audit)

- Create the experiment index by copy: `Copy-Item data\index.sqlite data\index.exp.sqlite`, then `$env:ARM_DATA_DIR` pointing at a folder containing it
  named `index.sqlite`. Never write vectors into the original until the final accepted build. Record the final rebuild command.
- Every reported configuration needs: git commit hash, the exact command, and the raw output block, saved under `docs/upgrade/runs/<rung>-<short-name>.txt`.
- Compare with `--compare` against the baseline JSONs; paste the delta table.
- Run each final configuration **twice** and confirm identical output (determinism).
- Keep a short `docs/upgrade/DECISIONS.md`: one entry per kept/rejected technique: what, measured effect on dev, effect on held-out, decision.

---

## 7. Work packages and file ownership

| WP | Does | Files it may edit | Depends on |
|---|---|---|---|
| WP-A | evaluator, validator, merge script, eval tests | `research/eval_retrieval.py`, `research/validate_eval_set.py`, `research/make_eval_v4.py`, `tests/test_eval_retrieval.py` | none |
| WP-B1/B2/B3 | write question fragments | `docs/upgrade/scratch/q_*.yaml` only | WP-A validator |
| WP-C | Rung 1 lexical | `src/ardupilot_research_mcp/query.py`, `glossary.vi-en.yaml`, `tests/test_query.py` | Phase 1 done |
| WP-D | model fetch, vector build | `research/build_vectors.py`, `research/build_all.py`, `src/ardupilot_research_mcp/ingest/` (new `embed_fetch.py`), `src/ardupilot_research_mcp/db.py` (add table only) | Phase 1 done |
| WP-E | dense query path + fusion | `src/ardupilot_research_mcp/dense.py` (new), `query.py` (after WP-C merges) | WP-D |
| WP-F | tests for fallback, determinism, safety-through-dense | `tests/test_dense.py` (new), `tests/test_offline.py` (extend allowed list only if truly needed, explain) | WP-E |
| WP-G | docs and gates | `README.md`, `README.vi.md`, `docs/*`, `CLAUDE.md`, `.github/workflows/ci.yml` | all |

Rule: WP-C and WP-E both touch `query.py`. Merge WP-C into the feature branch first; WP-E rebases on it.

Suggested order and parallelism: `WP-A` -> (`WP-B1`, `B2`, `B3` in parallel) -> merge/freeze/baseline -> (`WP-C` in parallel with `WP-D`; WP-D's embedding run is the long background job) -> `WP-E` -> `WP-F` -> `WP-G`.

---

## 8. Final gates (run all, paste raw output into the report)

```powershell
python -m pytest -q
python scripts\check_readmes.py
python scripts\check_traceability.py
python scripts\fidelity_scan.py                    # 0 mismatch
python scripts\check_param_citations.py            # 0 violations
python -m research.verify_citations                # PASS
python -m research.audit_safety                    # six required inputs OK
python scripts\bench.py                            # p95 <= 400 ms
python scripts\mutation_check.py                   # score must not drop; add mutants for new code if feasible
python -m research.eval_retrieval --set tests/golden.yaml --aggregate-only
python -m research.eval_retrieval --set tests/heldout_v3.yaml --aggregate-only
python -m research.eval_retrieval --set tests/eval_v4_heldout.yaml --aggregate-only --compare docs/upgrade/baseline/heldout.json <new.json>
python scripts\blackbox_run.py --out docs\upgrade\blackbox_after   # then compare with docs/blackbox/run3: 0 regressions required
```

Also run the dense-absent path: temporarily rename the `chunk_vectors` table on the **copy**, or unset the extras, and confirm every gate that does not need dense still passes.

**Acceptance for shipping dense retrieval as default:**

1. On held-out v4: overall **MRR improves by >= 0.05 absolute** and recall@5 does not drop, over the Phase 1 baseline.
2. **No category** loses more than 0.05 recall@5 or MRR (see the `--compare` table).
3. Vietnamese subset (including no-diacritics) recall@5 improves.
4. negative-pass-rate does not fall.
5. golden and v3 do not regress (>= baseline within 0.01).
6. Blackbox: 0 regressions. Safety: 0 false negatives, 0 false positives.
7. p95 latency budget holds; index growth and cold-start time are reported.

If 1-3 are not met, ship dense **off by default** (opt-in env var `ARM_DENSE=1`) and say so plainly in the report. Not meeting a target is an acceptable result;
hiding it is not.

---

## 9. Docs to update (WP-G)

- `README.md` and `README.vi.md`: new test count, eval v4 results table, "Optional: semantic retrieval" section, new env vars, new build stage. Keep both in sync.
  **`scripts/check_readmes.py` rejects em dashes, en dashes and stock AI phrases; run it.**
- `CLAUDE.md`: add the new files, the eval v4 rules, the `embeddings` extra, and the fallback behaviour. Keep it short.
- `docs/eval-v4.md`, `docs/license-notes.md` (model license), `docs/variant-4.6.md` (state whether the 4.6 variant gets its own vectors).
- `docs/blackbox/` etc.: do not rewrite history; add new runs under `docs/upgrade/`.

---

## 10. Final deliverable: `docs/upgrade/UPGRADE_REPORT.md`

Use exactly these sections so the audit is mechanical:

1. **Summary** (5 lines): what shipped, what did not, headline numbers.
2. **Phase 1 evidence**: counts table (category x lang x split), validator output, sha files, baseline tables.
3. **Phase 2 ladder**: one table row per rung/config: dev and held-out recall@5 / P@1 / MRR / chunk-hit@5 / negative-pass, delta vs baseline, p95 latency, decision.
4. **Per-category and per-language deltas** (paste `--compare` output).
5. **Gate results**: every command from section 8 with the raw result line.
6. **Decisions and rejected ideas** (link `DECISIONS.md`).
7. **Costs**: index size before/after, build wall time, cold-start time, dependency additions and licenses.
8. **Deviations from this brief** and why.
9. **Known limits and unverified claims**: be explicit.
10. **How to reproduce** (exact commands from a clean checkout plus the model download step).
11. **Commit list** (`git log --oneline` of the branch).

When finished: make sure `PROGRESS.md` is fully ticked, the branch is committed, `git status` is clean except gitignored data, and tell the owner
"ready for audit" with the branch name and the report path.

---

## 11. Common traps (learned from earlier rounds in this repo)

- A generator that printed the sampled topics burned a held-out set (v3 disclosure). Print counts and hashes only.
- Heading-based questions with duplicated headings cap recall by ambiguity, not by retrieval. Validate that ground truth is unique or list all valid files.
- BM25 can rank a near-duplicate paragraph above the true definition (the `0xBA` vs `0xD5` CRC case). Use `chunk-hit@5` and `answer_snippet` to catch wrong-chunk-right-file errors.
- Tests that need the gitignored corpus/index must skip themselves so fresh-clone CI stays green.
- `scripts/smoke_stdio.py` needs real stdio pipes; it fails with `WinError 5` inside a sandbox.
- On Windows git over HTTPS may need `git -c http.sslBackend=openssl ...`.
- Do not report numbers from memory of earlier runs. Re-run.
