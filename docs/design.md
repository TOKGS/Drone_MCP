# Design — ardupilot-research-mcp (one page)

## Goal and non-goals

**Goal:** a local, read-only MCP server (stdio) that answers ArduPilot development questions with
version-pinned, machine-checkable citations, works fully offline after ingest, and understands
Vietnamese questions against English sources.

**Non-goals:** flashing, arming, parameter writes, serial/vehicle I/O, telemetry streaming,
any network at serve time, any multi-version matrix (v1 pins the latest release of each repo).

## Three zones, enforced by tests

| zone | network | imports allowed | shipped |
|---|---|---|---|
| `research/` | yes (build only) | `urllib`, `sqlite3`, `yaml` | no — build tooling |
| `src/ardupilot_research_mcp/ingest/` | yes (build only) | same as above | recipe only |
| `src/ardupilot_research_mcp/` (server, tools, decoders) | **no** | stdlib + `mcp` + `yaml` | yes |

`tests/test_offline.py` fails the build if `src/` (outside `ingest/`) imports
`requests`, `urllib`, `socket`, `http.client`, `ssl`, `subprocess`, or calls
`os.system`/`eval`/`exec`.

## Storage

One SQLite file, `data/index.sqlite`:

- `sources` — id, repo, ref (tag/SHA), tier, license, retrieved_at, manifest_sha256
- `documents` — id, source_id, path, sha256, lang, bytes
- `chunks` — id, document_id, ord, text, heading_path, anchor, line_start, line_end, sha256
- `chunks_fts` — FTS5 external-content index over `chunks.text` (+ heading path), BM25 ranking
- `params` — vehicle, version, name, unit, range, default, reboot_required, values, bitmask, chunk_id
- `mavlink_msgs`, `mavlink_enums` — id/name/fields/enum entries with `chunk_id`

BM25 alone must be sufficient; embeddings are an optional extra table, never required.

## Citation contract

`cite_id = "<source_id>#c<chunk-ordinal>"`. Every citation carries repo, SHA-pinned permalink
(`.../blob/<sha>/<path>#L<a>-L<b>`, never `main`), path, line range, version label, tier,
license, `retrieved_at`, a verbatim excerpt (≤600 chars), and `untrusted: true`.
`cite.py::verify_quote(cite_id, text)` re-reads the stored chunk and asserts the excerpt is a
substring; a test asserts this for **every** excerpt every tool can emit.

## Trust tiers

T1 authoritative (source, wiki, MAVLink XML, ELRS/EdgeTX source) · T2 issue/PR evidence ·
T3 forum symptom evidence (always `symptom_evidence_only: true`).
A parameter/bit/message claim is only admitted with a T1 source.

## Language handling

Vietnamese question → `glossary.vi-en.yaml` expansion (editable) → BM25 over English expansion
with identifier boost (`RC_OPTIONS`, `SERIAL_ORDER` exact match weighted above prose).
Answers keep English excerpts verbatim and may add a one-line `summary_vi` derived only from
the excerpt text.

## Safety

Any procedure touching hardware carries `Props off for bench tests. SITL before hardware.`
plus a `CONFIRM:` line. `ARMING_CHECK=0`, force-arm and disabled failsafe/fence are never
presented as fixes — they are flagged as dangerous. Prompt-injection fixtures live in tests.

## Search-quota governance (deviation, deliberate)

`research/governor.py` owns every external call: SQLite WAL ledger, sliding window with 20 %
headroom, min interval, per-provider cost budget, cache-first, `Retry-After`, exponential
backoff, circuit breaker, `STATE.md` on exhaustion. An LLM subagent cannot be forced through a
Python wrapper, so the **coordinator alone holds provider tools**; subagents receive cached
files and topic briefs. Enforced by convention plus the ledger acting as the audit trail.

## Corpus acquisition (verified this build)

Latest pin per repo, tarballs fetched with 0 search quota, filtered by `sources.yaml` globs:
4885 files / 51.1 MB (ardupilot 2702, wiki 1609, mavlink 43, expresslrs 422, edgetx 109).
Licenses read from each archive's own license file — see `docs/license-notes.md`.
MAVLink XML definitions carry no upstream license statement; flagged for a user decision.

## Failure modes

`index not built: run ingest` · `found: false` + nearest candidates (never a fabricated name) ·
quota stop → `research/STATE.md` + resume from cache · output cap 24 KB (guard.py) with a clear
"slow down" error instead of silent truncation.
