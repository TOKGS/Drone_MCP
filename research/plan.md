# Research plan — ardupilot-research-mcp

Written by the coordinator after §2.1 (limits established) and before any search call.
Budget agreed with the user: **300 Firecrawl credits, 100 Exa calls, 40 built-in web_search calls.**

## Limits in force (research/limits.yaml)

| provider | req/h | headroom 20% | effective/h | min interval | budget |
|---|---|---|---|---|---|
| firecrawl | 20 (ASSUMED) | 4 | **16** | 5 s | 300 credits (1106 available) |
| exa | 20 (ASSUMED) | 4 | **16** | 5 s | 100 calls |
| web_search | 20 (ASSUMED) | 4 | **16** | 5 s | 40 calls |
| github / codeload | 60 / 30 | — | 48 / 24 | 1–2 s | unmetered (tarball, raw) |

ASSUMED rows are labelled in `limits.yaml`; the governor honours `Retry-After` and any
header-reported remaining quota, which override these estimates.

## Cost ladder applied

1. `ledger.sqlite` + `cache/` (free).
2. `codeload.github.com` tarballs at pinned tags and `raw.githubusercontent.com`
   raw files — **0 search quota**, resolves most of the corpus.
3. Exa — discovery only (which URL, which repo path, which issue).
4. Firecrawl — pages that only exist rendered (T3 forum threads, docs sites).
5. Built-in `web_search` — fallback discovery only.

## Version policy (user decision)

**Latest release only, one pin per source, no multi-version matrix.** Each source gets one
tag/SHA in `sources.yaml`; every answer states that single version. Version matrix support
stays a documented extension point, not a v1 feature.

## Waves and estimated spend

| Wave | Topic | Tier | exa | firecrawl | web | credits |
|---|---|---|---|---|---|---|
| 1-A | MCP spec + Python SDK 1.30.0 + client config formats (OpenCode, Claude Code, Codex) | 1 | 4 | 8 | 0 | 8 |
| 1-B | Corpus inventory, licenses, offline acquisition method per source | 1 | 6 | 2 | 0 | 2 |
| 1-C | ArduPilot param/bitmask metadata, MAVLink definitions, latest tags | 1 | 3 | 0 | 0 | 0 |
| 1-D | ESP32 HAL, RC/CRSF/ELRS troubleshooting evidence | 1 | 8 | 25 | 2 | 25 |
| 1-E | Retrieval/eval design, FTS5 (verified locally), Vietnamese handling | 2 | 3 | 4 | 0 | 4 |
| 2 | Ingest pipeline, chunkers, DB, decoders, tests (zero quota, disjoint files) | 1 | 0 | 0 | 0 | 0 |
| 3 | Verification pass over cached text (zero quota) | 1 | 0 | 0 | 0 | 0 |
| — | **Reserve for verification + gap-filling (15%)** | — | 4 | 6 | 1 | 6 |
| | **Total** | | **28** | **45** | **3** | **45** |

Wall-clock at the assumed limits: Firecrawl ~3 h serialised, Exa ~2 h; both run in
parallel with 0-quota work, so the build is not quota-bound.

## If the estimate is exceeded

Trim in this order (lowest value first), and say so in the final report:

1. T3 forum threads beyond the top-20 symptoms in `troubleshoot`.
2. Rendered doc pages that also exist as raw markdown in a repo tarball.
3. EdgeTX / ExpressLRS **source** (keep their docs only).
4. Wave 1-E evaluation research (FTS5 already verified working locally).

## Enforcement boundary (deviation, stated explicitly)

The spec assumes subagents call a Python `guarded_call` wrapper around provider tools.
An LLM subagent cannot be forced through a Python wrapper — it calls MCP tools directly.
Therefore:

- **Only the coordinator holds provider tools** (exa / firecrawl / web_search).
- Subagents receive **cached files and topic briefs**, never search credentials or tools.
- Every network call the coordinator makes is either (a) executed by
  `research/governor.py` directly, or (b) executed through an MCP tool and recorded with
  `governor record` immediately after, with the same reservation id.

This keeps the ledger authoritative and the quota enforceable. It is recorded in
`docs/design.md` when that file is written.

## Ordered checkpoints

1. ✅ limits established, governor built, 11 tests green, ledger empty.
2. ⏳ resolve the latest tag of each source (1 GitHub API call each, recorded), then fetch
   tarballs/raw (0 search quota) and write `sources.yaml` + `docs/license-notes.md`.
3. Wave 1 research through the governor → `research/findings/<topic>.json`.
4. `verify_findings` (zero quota) → `research/verification.md`.
5. Ingest + DB + chunkers on a small subset; citations verified end to end.
6. Tools in the §8 order; golden questions; offline/security tests; README; final report.
