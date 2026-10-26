# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

`ardupilot-research-mcp`: a local, offline, **read-only** MCP server (stdio, `mcp==1.30.0`, Python >=3.10) that answers ArduPilot / ExpressLRS / EdgeTX / CRSF / MAVLink questions from a pinned corpus and returns verifiable citations. The workspace root `D:\Skill_tulan` is not the repo; this directory is (own `.git`). `_skill-backup-*` and `.bundle/` next to it are unrelated. `README.md` is the authoritative user doc; `HANDOFF.md` is historical and its numbers are superseded (see `docs/FIX_REPORT.md`).

## Commands

```powershell
pip install -e ".[dev]"
pip install -e ".[embeddings]"                        # optional: onnxruntime, tokenizers, numpy for dense
python -m pytest -q                                   # full suite (corpus-dependent tests skip themselves)
python -m pytest tests/test_params.py -q              # one file
python -m pytest tests/test_safety.py::test_name -q   # one test
python -m ardupilot_research_mcp.server               # stdio server; prints nothing, waits for a client
```

CI (`.github/workflows/ci.yml`) runs on a fresh clone with **no index and no corpus**: `pytest -q`, `scripts/check_readmes.py`, `scripts/check_traceability.py`. Run all three before finishing a change. `check_readmes.py` also lints `README.md`/`README.vi.md` (no AI-writing tells, numbers must agree) — if you change counts in one README, change the other and the doc numbers.

Index build (needs network once, ~5 min, ~3 GB disk; `data/` and `research/cache/` are gitignored):

```powershell
python -m research.build_all --gates        # fetch -> extract -> ingest -> params -> mavlink -> gates; stops at first failing stage
python -m research.build_all --dry-run      # print the stage commands
# or manually: research.fetch tags|download, research.extract, ardupilot_research_mcp.ingest.cli --all --rebuild-index,
#              research.build_params, research.build_mavlink, ardupilot_research_mcp.ingest.cli --verify
python -m research.build_vectors                      # optional stage: 68 min, 63 MB; skipped without the model
python -m research.build_doc_vectors --index data\exp\index.sqlite   # optional V2 prior: 2.8 min, 5.4 MB
```

Gates (need the built index): `scripts/fidelity_scan.py`, `scripts/check_param_citations.py`, `scripts/bench.py`, `python -m research.verify_citations`, `python -m research.audit_safety`, `scripts/mutation_check.py`, and the eval sets: `tests/golden.yaml` (tunable), `tests/heldout_v3.yaml`, `tests/eval_v4_dev.yaml` (tunable), `tests/eval_v4_heldout.yaml` (frozen, one run per kept configuration), `tests/eval_v4_neg_vi.yaml`. `scripts/smoke_stdio.py` needs real stdio pipes (fails with WinError 5 in a sandbox).

## Architecture

**Two phases, strictly separated.** Build time (`research/` scripts + `src/ardupilot_research_mcp/ingest/`) downloads pinned archives and writes `data/index.sqlite`. Answer time reads **only** that SQLite file. `ingest/` is the only package allowed to import network modules; `tests/test_offline.py` enforces this, plus no `shell=True`/`eval`/`exec` and no hardcoded `X.Y.Z` release versions in `src/`. `tests/test_distil.py` deletes the corpus and checks tools still answer.

**Server wiring** (`server.py`): only registers the 14 tool functions with `FastMCP` and a shared `READ_ONLY` annotation. stdout is the protocol channel — never `print()` in `src/`; diagnostics go to stderr.

**Tools** (`tools/<name>.py`): one function per module, first arg is the sqlite connection. Every tool is wrapped by `tools/_base.py`: `@guarded` (index-backed) or `@guarded_pure` (decoders, no index). The wrapper provides the 60 calls/min rate guard (`guard.py`), the per-argument length limits in `_base.LIMITS` (violations return `{"found": false, "max_length": N}`, not a pydantic error), the "index not built" error, response capping (3 excerpts per source, 600 chars each, 24 KB total), and converts unexpected exceptions into `{"found": false, "error": "internal error", "error_id"}` with the traceback on stderr. The wrapper rewrites `__signature__` to drop the connection arg and inject `maxLength` into the JSON schema. When adding/changing a tool, add its entry to `LIMITS` and to the tuple in `server.py`. `decode_crsf_frame` is deliberately absent from `LIMITS` (its limit is a pydantic `max_length`, so oversize input yields a schema error instead of a `found:false` payload — known inconsistency).

**Retrieval** (`query.py`): query normalised for Vietnamese chat spellings (`vi.py`: "ko" -> "không", "dc" -> "được", repeated letters; ambiguous ones only with Vietnamese evidence, so "DC motor" is left alone), folded for case/diacritics, expanded with `glossary.vi-en.yaml` per token (a multi-word key also matches with diacritics folded, so "khong arm duoc" fires "không arm được"), stopworded; a corpus anchor gate (rare words / known `snake_case` symbols) returns `found:false` for out-of-scope questions (`scope.yaml` lists out-of-corpus products); FTS5 (BM25) over `chunks.distilled` plus a literal-identifier pass; per-document scoring with path/heading boosts and a penalty for `libraries/SITL/`. `chunks.distilled` exists only for FTS; `chunks.text` must stay a **byte-verbatim** slice of the pinned file, because citations quote it. Do not "clean" `chunks.text`.

**Optional dense retrieval** (`dense.py`): `research/build_vectors.py` embeds `chunks.distilled` with e5-small ONNX into `chunk_vectors` (float16, 384 dims, 63 MB). `query.search` reranks the BM25 candidates by cosine only when `ARM_DENSE=1`; otherwise the BM25 path runs exactly as before. The model lives under `data/models/multilingual-e5-small/` (`ARM_MODEL_DIR` overrides). `research/build_doc_vectors.py` writes one vector per document (`doc_vectors`, path words plus heading paths) for the V2 topic prior, which measured worse on both dev sets and is off unless `ARM_DOC_PRIOR=1`. Missing table, model or dependency always falls back to BM25, and `index_status` reports `dense.state` plus `unavailable_reason`; `ARM_DENSE=1` with missing assets prints one warning naming the reason. It is off by default because it lost on held-out v4 (`docs/upgrade/rung2.md`).

**Citations** (`cite.py`): `cite_id = <source_id>#sha256(source_id|path|line_start|line_end|sha256(text))[:16]`, pinned permalink (tag or full SHA, never a branch), line range, excerpt <=600 chars, `untrusted: true`. Channel rules: tag -> `stable`; commit SHA -> `snapshot` + `unreleased`; local overlay -> `local`, `pinned:false`, `url:null`, visible only with `scope="local"` and excluded from recall numbers.

**Safety gate** (`safety.py` + `safety_rules.yaml`, used by `troubleshoot`): rules are data. Matching runs on diacritic-folded text so Vietnamese and English phrasings hit the same rule. Requests to disable/mask arm checks, failsafes or fences are refused with a safe path; dangerous-recipe excerpts are filtered from citations; bench procedures must carry `Props off for bench tests. SITL before hardware.` Change behaviour by editing the YAML, then run `tests/test_safety.py`, `tests/test_safety_cases_v2.py` (`tests/safety_cases_v2.yaml`) and `python -m research.audit_safety`. `tests/test_safety_vi_chat.py` pins seven Vietnamese chat-style (no diacritics, abbreviations) bypass requests and three informational questions; a zeroing request without an equals sign ("dat arming check 0 dc ko") is a known gap, not covered by the rules. Never add output that prints `ARMING_CHECK=0`-style bypass recipes.

**Parameter / MAVLink / board data:** `research/build_params.py` parses `@Param/@Bitmask/@Default` blocks (resolving `@Group`/`@Path` prefixes and instance families) into the `params` table; `build_mavlink.py` fills message/enum tables from XML. `default_raw` is verbatim; `default` is set only when resolvable to a literal/single `#define`, otherwise `default_resolved:false` — report, don't guess. `decoders/` (CRSF, Intel HEX) are stdlib-only and derived from the corpus (CRC8 poly 0xD5, `(ticks-992)*5/8+1500` with C-style truncating division).

**Config** (`config.py`, env vars): `ARM_REPO_ROOT` (where `sources.yaml`/glossary/scope live), `ARM_DATA_DIR` (index, corpus, local), `ARM_SOURCES` (alternate pin set; `sources-4.6.yaml` builds the ArduPilot 4.6.2 variant into `data/4.6`, see `docs/variant-4.6.md`), `GOVERNOR_HOME` (quota ledger). Caches `load_sources` with `lru_cache`.

**Quota governor** (`research/governor.py`): any metered source (Firecrawl, Exa, web search, GitHub API) must be spent via reserve -> call -> record through the governor's SQLite ledger. The current corpus is built from `git ls-remote` + codeload archives, which spend no search quota.

## Test and eval conventions

- `tests/conftest.py` resets the in-process rate guard between tests; the production limit is unchanged. A test hitting >60 tool calls/min in one process otherwise fails by order.
- Frozen eval sets are SHA-256-pinned (`docs/heldout*.sha256`); `research.eval_retrieval` refuses to run if a set changed. Do not edit `tests/heldout_*.yaml` or `tests/blackbox_cases.md`. `golden.yaml` is the tunable dev set (not evidence); `heldout_v3.yaml` is the fair blind set. Do not tune retrieval to specific held-out questions.
- `tests/test_params.py`-style tests and `check_param_citations.py` assume the built index; corpus-comparing tests skip when `data/corpus` is absent.
- `tests/test_hardening.py` link-escape test skips on accounts that can't create directory symlinks.
- `scripts/check_traceability.py` maps requirements -> tests; if you rename a test referenced there, update the mapping.
- Eval v5-vi (`docs/eval-v5-vi.md`): 120 Vietnamese questions, `tests/eval_v5_vi_dev.yaml` (49, tunable) and `tests/eval_v5_vi_heldout.yaml` (71, frozen by `docs/eval-v5-vi-heldout.sha256`, one run per kept configuration). `research/make_eval_v5.py` merges the fragments and refuses a question that re-uses a v4 one; `research/validate_eval_set.py --strict-v5 --cross-check` enforces the v5 rules. Every run also splits by `script` (ascii-only vs diacritics, read from the question text) and by `lang`.
- Eval v4 (`docs/eval-v4.md`): 125 questions written from corpus evidence, split into `tests/eval_v4_dev.yaml` (53, tunable) and `tests/eval_v4_heldout.yaml` (72, frozen by `docs/eval-v4-heldout.sha256`), plus `tests/eval_v4_neg_vi.yaml` for Vietnamese negatives. Tune on dev only. A kept configuration gets **exactly one** held-out run; every comparison table shows the Phase 1 baseline, Rung 1 and the candidate. `--compare old.json new.json` prints the per-category and per-language deltas.
- Write files with LF. On Windows a text-mode write turns `\n` into `\r\n`; that once corrupted `docs/upgrade/PROGRESS.md`. Open with `newline="\n"`, or read bytes and write bytes. `README.md` and `README.vi.md` are CRLF in git: read them with universal newlines and write them back with `newline="\r\n"` so the diff stays small.

## Gotchas

- `.mcp.json` is per-machine and gitignored; edit `.mcp.json.example` for the committed template.
- On Windows, `git: schannel: SEC_E_NO_CREDENTIALS` -> `git -c http.sslBackend=openssl ...`.
- README/docs contain many measured numbers (chunks, params, test counts). After changes that move them, rerun the relevant gate and update README.md, README.vi.md and `check_readmes.py` expectations together.
