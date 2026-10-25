# ardupilot-research-mcp

**A local, read-only MCP server that answers ArduPilot / ExpressLRS / EdgeTX / CRSF / MAVLink
questions from a pinned, offline corpus — and returns a machine-checkable citation for every
documentary answer.**

It never arms, flashes, erases, writes parameters, opens a serial port or talks to a vehicle, and it
makes **no network calls at serve time**. Every answer either carries a `cite_id` + permalink +
exact line range + verbatim excerpt, or says `found:false`.

```
$ python -m ardupilot_research_mcp.server          # stdio MCP server, 14 tools
$ python -m pytest -q                              # 133 passed
```

Repo: `github.com/TOKGS/Drone_MCP` · package: `ardupilot-research-mcp` v0.1.0 · Python ≥ 3.10

> **Tiếng Việt, ngắn gọn:** đây là MCP server chạy nội bộ, chỉ đọc, trả lời câu hỏi kỹ thuật
> ArduPilot kèm trích dẫn kiểm chứng được (`cite_id`, URL ghim SHA/tag, đúng số dòng, excerpt ≤ 600
> ký tự khớp nguyên văn nguồn). Không có mạng lúc trả lời, không điều khiển drone, không bao giờ
> khuyên tắt kiểm tra an toàn. Cài đặt + dựng index + đăng ký client: xem **Quick start**.

---

## Contents

1. [What it is / is not](#1-what-it-is--is-not)
2. [Guarantees](#2-guarantees)
3. [Quick start](#3-quick-start)
4. [Tool reference (14 tools)](#4-tool-reference-14-tools)
5. [Citation contract](#5-citation-contract)
6. [Corpus and pins](#6-corpus-and-pins)
7. [Parameters](#7-parameters)
8. [Safety policy](#8-safety-policy)
9. [How retrieval works](#9-how-retrieval-works)
10. [Configuration](#10-configuration)
11. [Quota governance](#11-quota-governance)
12. [Register it in a client](#12-register-it-in-a-client)
13. [Tests and gates](#13-tests-and-gates)
14. [Measured quality](#14-measured-quality)
15. [Reproduce the whole build](#15-reproduce-the-whole-build)
16. [Layout](#16-layout)
17. [Troubleshooting](#17-troubleshooting)
18. [Known limitations and unverified claims](#18-known-limitations-and-unverified-claims)
19. [Licenses and provenance](#19-licenses-and-provenance)
20. [Status and changelog](#20-status-and-changelog)

---

## 1. What it is / is not

**It is** a knowledge server for people writing or debugging ArduPilot code, wiring a flight
controller, decoding a CRSF frame, reading a `hwdef.dat`, checking an Intel HEX file, or asking why
a parameter does not exist at a release tag. The corpus is the actual firmware source, wiki, MAVLink
XML, ExpressLRS source/docs, EdgeTX and the CRSF spec at **pinned refs** — not model memory.

**It is not** a control channel, a parameter writer, a firmware flasher, a Mission Planner
replacement, or a general search engine. There is no tool that mutates anything, and there is no
fallback to "probably true" when the corpus has no answer.

| You ask | You get |
|---|---|
| `lookup_param("RC_OPTIONS")` | the declaring `@Param` block, its `@Bitmask` bits, `default_raw` → resolved `default` (32), pinned permalink |
| `decode_bitmask("RC_OPTIONS", "0x2000")` | `bit 13 SET: Use 420kbaud for ELRS protocol` — parsed from the pinned header |
| `mavlink_message("HEARTBEAT")` | msgid 0, fields, CRC extra, `common.xml` citation |
| `decode_crsf_frame("C8 18 16 …")` | 16 × 11-bit channels, CRC8 validity, µs via the spec's `TICKS_TO_US` macro, truncation info |
| `check_intelhex_line(":1001…40")` | checksum valid/3 invalid, record type, data bytes |
| `troubleshoot("tắt failsafe để nó khỏi báo")` | **refusal** + why dangerous + a safe path, never the disabling recipe |
| `search_docs("giá bitcoin hôm nay")` | `found:false` + out-of-scope note — not five confident-looking hits |

---

## 2. Guarantees

| # | Guarantee | Enforced by |
|---|---|---|
| 1 | **Read-only.** All 14 tools carry `readOnlyHint=true, idempotentHint=true, openWorldHint=false`; no write path exists in `src/`. | `src/ardupilot_research_mcp/server.py`, `tests/test_offline.py` |
| 2 | **Offline at serve time.** Answering reads `data/index.sqlite` only; corpus files are not read, no network module is imported outside `ingest/`. | `tests/test_distil.py` (corpus deleted, tools still answer), `tests/test_offline.py` |
| 3 | **Every excerpt is real.** Chunk text is a byte slice of the pinned file; the full scan compares all 86 262 chunks against the Git blob. | `scripts/fidelity_scan.py`, `research/audit_git.py` |
| 4 | **Pins, not branches.** URLs point at a tag or a full commit SHA — never `main`/`master`/`HEAD`. | `research/verify_citations.py` (0 unpinned URLs) |
| 5 | **No invented names.** Unknown parameter/board/message → `found:false` plus real candidates from the index; a rename that the release notes record is returned as `renamed_hint`. | `tests/test_params.py`, `tests/test_mavlink_board.py`, blackbox B1/B3 |
| 6 | **Safety first.** Requests to disable/mask arm checks, failsafes, fences or to force-arm are refused with a safe path; hardware procedures carry `Props off for bench tests. SITL before hardware.` | `safety.py` + `safety_rules.yaml`, `tests/safety_cases_v2.yaml`, `research/audit_safety.py` |
| 7 | **Excerpts are data, not instructions.** Every citation is `untrusted: true`; the server never follows text found in the corpus. | `cite.py`, server instructions |
| 8 | **No silent failure.** Oversized input → explicit `max_length` error; unexpected exception → `{"found":false,"error":"internal error","error_id":"…"}` with the detail on stderr only. | `tools/_base.py`, `tests/test_query.py` |

---

## 3. Quick start

### 3.1 Install

```powershell
git clone https://github.com/TOKGS/Drone_MCP.git ardupilot-research-mcp
cd ardupilot-research-mcp
python -m venv .venv; .\.venv\Scripts\Activate.ps1
pip install -e .
```

```bash
# Linux / WSL — identical, with python3
python3 -m venv .venv && . .venv/bin/activate && pip install -e .
```

Dependencies are only `mcp==1.30.0` and `pyyaml` (plus `pytest` for the dev extra). The MCP SDK is
pinned because the tool schema surface was verified against exactly that version
(`docs/research-notes.md`).

### 3.2 Build the index (the only networked phase)

```powershell
python -m research.fetch tags        # resolve the newest Copter-X.Y.Z tag with git ls-remote (no beta/rc)
python -m research.fetch download    # download the pinned archives (0 search-quota units)
python -m research.extract           # filtered corpus -> data/corpus
python -m ardupilot_research_mcp.ingest.cli --all --rebuild-index
python -m research.build_params      # @Param / @Bitmask / @Default -> params table
python -m research.build_mavlink     # MAVLink XML -> messages + enum tables
python -m ardupilot_research_mcp.ingest.cli --verify
```

Expect ≈ 5 min and a **≈ 182 MB** `data/index.sqlite` on a laptop: 7 356 documents → 86 262 chunks →
5 089 parameters → 397 MAVLink messages / 2 367 enum entries.

`--resume` (default) skips files already indexed by hash; `--rebuild-index` recreates the SQLite file.

### 3.3 Try it without a client

```powershell
$env:PYTHONPATH = "src"
python -c "import sys; sys.path.insert(0,'src'); from ardupilot_research_mcp.tools.lookup_param import lookup_param; import json; print(json.dumps(lookup_param('RC_OPTIONS'), ensure_ascii=False, indent=1)[:1500])"
```

### 3.4 Register it (then ask a question)

See [§12](#12-register-it-in-a-client). First questions that exercise the citation contract:

```
lookup_param("ARMING_SKIPCHK")
decode_bitmask("RC_OPTIONS", "0x2000")
decode_crsf_frame("C81816E0031FF8C0073EF0810F7CE0031FF8C0073EF0810F7CAD")
check_intelhex_line(":10010000214601360121470136007EFE09D2190140")
troubleshoot("what does FS_THR_ENABLE do, and which value means disabled?")
```

---

## 4. Tool reference (14 tools)

All tools are pure functions in `src/ardupilot_research_mcp/tools/<name>.py`, wrapped by a shared
guard that (1) rate-limits to 60 calls/min, (2) rejects oversized input **before** touching SQLite,
(3) caps the response (≤ 3 excerpts per source, ≤ 600 chars each, ≤ 24 KB total), and
(4) converts unexpected exceptions into `internal error` + `error_id`.

| Tool | Arguments | Returns |
|---|---|---|
| `search_docs` | `query` (≤ 2000), `scope` = `all\|docs\|code\|protocol\|dev\|local`, `version`, `tier_max`, `limit` (default 8) | ranked documents with citations, `scope_notes`, `confidence`, `note` |
| `get_chunk` | `cite_id`, `context_lines` | the chunk text plus neighbours, with the same citation object |
| `lookup_param` | `name_or_pattern`, `vehicle` (default ArduCopter), `version` | `params[]` with `display_name`, `enum_values`, `bitmask`, `default_raw`, `default`, `default_resolved`, `renamed_hint`, citation |
| `decode_bitmask` | `param`, `value` (number or bit names) | decoded bits → names, or names → value; independence cross-checked against `@Bitmask` |
| `find_source` | `symbol_or_file`, `repo`, `version` | defining path + pinned permalink + citation |
| `board_info` | `board_name`, `hal` | parsed `hwdef.dat` facts: MCU, `SERIAL_ORDER`, RC defines, DMA hints, `included_files` |
| `mavlink_message` | `name_or_id` (`HEARTBEAT`, `0`, or an enum entry) | message fields, CRC extra, enum values, `common.xml` citation |
| `troubleshoot` | `symptom`, `context` | either evidence-backed triage **or** a refusal with `dangerous`, `refused_as_fix`, `message`, `safe_path`, `why_dangerous` |
| `get_script` | `topic` | a complete runnable example from `examples/`, its `cite_ids` and run commands |
| `decode_crsf_frame` | `hex` (≤ 4096 chars) | frames, `frames_found`, `all_crc_valid` (`null` when 0 frames), per-channel µs, `truncated_tail_bytes` |
| `check_intelhex_line` | `line` (≤ 600 chars) | start code, byte count, checksum valid/invalid, record type |
| `parse_ihex_summary` | `path` (inside `data/` only, ≤ 1024) | record counts by type, data bytes, address span, EOF presence |
| `list_sources` | — | every source with pin, tier, license and document count |
| `index_status` | — | counts (`sources/documents/chunks/params`), size, last ingest, offline note |

`scope`: `docs` = wiki + ExpressLRS docs, `code` = firmware source, `protocol` = MAVLink + CRSF,
`dev` = ArduPilot dev wiki, `local` = your own unpinned board files (never in recall numbers),
`all` = everything except `local`.

---

## 5. Citation contract

```jsonc
{
  "cite_id": "ardupilot#1a2b3c4d5e6f7a8b",      // <source_id>#<hash16>
  "source_id": "ardupilot",
  "repo": "ArduPilot/ardupilot",
  "ref": "Copter-4.7.2",                        // tag or full commit SHA
  "channel": "stable",                          // stable | snapshot | local
  "unreleased": false,
  "pinned": true,
  "url": "https://github.com/ArduPilot/ardupilot/blob/Copter-4.7.2/libraries/RC_Channel/RC_Channels_VarInfo.h#L92-L97",
  "path": "libraries/RC_Channel/RC_Channels_VarInfo.h",
  "lines": [92, 97],
  "excerpt": "…verbatim slice, ≤ 600 chars…",
  "version": "Copter-4.7.2 (2026-10-20)",
  "ingested_at": "2026-10-25T20:13:33+0700",
  "tier": "T1",
  "license": "GPL-3.0",
  "untrusted": true
}
```

- `cite_id` is **content-addressed**: `sha256(source_id | path | line_start | line_end | sha256(text))`
  truncated to 16 hex chars. Re-ingesting the same text yields the same id; changing the text changes
  the id.
- `get_chunk(cite_id)` returns the same text the citation promised — the blackbox run checked 20/20
  with `field_diff = 0`.
- Channel rules: a **tag** pin → `channel:"stable"`; a **commit** pin → `channel:"snapshot"` +
  `unreleased:true`; `local-project` → `channel:"local"`, `pinned:false`, `url:null`.
- Every excerpt is capped at **600 characters** and flagged `untrusted:true`.

---

## 6. Corpus and pins

`sources.yaml` is the single source of truth: repo, ref (tag or SHA — never a branch), tier, license
and include/exclude globs. `research.fetch tags` resolves the newest `Copter-X.Y.Z` tag with
`git ls-remote --tags --refs` and rejects beta/rc — no version is hardcoded in `src/`
(`tests/test_offline.py::test_no_hardcoded_release_version_outside_tests`).

| Source | Repo | Pin | Tier | License |
|---|---|---|---|---|
| `ardupilot` | ArduPilot/ardupilot | `Copter-4.7.2` → `fb77356789…` | T1 | GPL-3.0 |
| `ardupilot_wiki` | ArduPilot/ardupilot_wiki | `828de1f225dace34b482e63abaab15d25b2b1732` | T1 | CC-BY-SA-3.0 |
| `mavlink` | mavlink/mavlink | `eec8824212c1fe8c5d8f5181fcfdef54ee219b63` | T1 | unstated (kept labeled) |
| `expresslrs` | ExpressLRS/ExpressLRS | `4.1.0` → `a9d4a9cb5b5687c4c9d7e9e7fbdf44ad93651da6` | T2 | GPL-3.0 |
| `expresslrs_docs` | ExpressLRS/ExpressLRS | `5ed656b6ebc7a38b6012297cf40fe5bc87232bed` | T2 | GPL-3.0 |
| `edgetx` | EdgeTX/edgetx | `v2.12.5` → `0ebe2e98b2085e2251ad6773b26c8a7ab8dd3e99` | T2 | GPL-2.0 |
| `crsf_spec` | (CRSF spec mirror) | `a73f7dc5386e5b8744aa4a23b3af5354ee0d4c92` | T2 | CC-BY-SA-4.0 |
| `local-project` | *your files* | `local` | T3 | user-owned |

Indexed slice today: **7 sources → 7 356 documents → 86 262 chunks**, index **182.3 MB**.
Per-source counts are in `list_sources`. Licenses per source were read from each archive's own
license file (`docs/license-notes.md`); the corpus itself is **never committed** (`data/` and
`research/cache/` are gitignored).

The include list covers every `libraries/*` that declares `// @Param` metadata at the pin, which is
what makes parameter lookups complete — see §7.

---

## 7. Parameters

`lookup_param` answers from **`@Param` / `@Bitmask` / `@Default` metadata in the pinned source**, not
from a hand-written list:

- **5 089 parameter names** from **2 070 `@Param` blocks**; full names are resolved through the
  pinned `@Group` / `@Path` chain (e.g. `@Param: 1_PROTOCOL` in `AP_SerialManager.cpp` + prefix
  `SERIAL` → `SERIAL1_PROTOCOL`), so instance families (`RC1..RC16`, `SERIAL1..8`, `BATT`/`BATTA`,
  `INS`/`INS2`/`INS3`, `COMPASS2/3`, `OSD1..5`) expand correctly. No row is a duplicate: 0 rows share
  `(path, line_start, prefix)`.
- **Defaults**: `default_raw` is the verbatim `@Default:` argument (**4 703 / 5 089** rows), resolved
  to a number only when it is a literal, a bit expression, or exactly one in-corpus `#define` —
  **3 003 resolved**, **1 700 left unresolved** (macro chains, functions, `-1` sentinels) rather than
  guessed. Example: `FS_THR_ENABLE → 1` (`FS_THR_ENABLED_ALWAYS_RTL`), `FS_THR_VALUE → 975`,
  `RC_OPTIONS → 32` (`(1U<<5)`), `ARMING_SKIPCHK → 0`; `LOG_BITMASK` keeps
  `default_raw=DEFAULT_LOG_BITMASK` with `default_resolved:false`.
- **Citations point at the parameter's own block**: every one of the 5 089 rows is machine-checked so
  the excerpt contains `@Param:<suffix>` and the line range covers it — **0 violations**
  (`scripts/check_param_citations.py`). Before this was fixed, 3 891/5 089 citations showed a
  neighbouring block.
- **Renames are reported, not silently missed**: `ARMING_CHECK` → `found:false` +
  `renamed_hint{new:"ARMING_SKIPCHK", path:"ArduCopter/ReleaseNotes.txt"}`; `WPNAV_SPEED` →
  `found:false` with no hint (the release notes do not record that rename).
- **Coverage measured against real usage**: of **1 440** unique names used by
  `Tools/autotest/default_params/*.param` and `Tools/Frame_params/*.param` at the pin, **739 (51.3 %)**
  are found; the rest are mostly other vehicles' frames (classified in `docs/fix/A-names.txt`).
- Unresolvable cases are listed, not invented: **509 unresolved blocks** + **142 unlinked blocks**
  (`docs/fix/A-unresolved.txt`).

---

## 8. Safety policy

The server explains safety systems; it never presents disabling one as a fix.

- **Rules are data**, in `src/ardupilot_research_mcp/safety_rules.yaml`: `disable_verbs`,
  `safety_objects`, `safety_params`, `value_patterns`, `info_markers`, `hardware_markers`,
  `dangerous_excerpt`. Matching runs on folded text (lowercase, diacritics stripped), so
  "tắt failsafe", "tat failsafe" and "turn the failsafe off" hit the same rule.
- **Decision**: `(disable_verb ∧ safety_object) ∨ (safety_param ∧ zeroing_pattern)` → **REFUSE**,
  even inside a question. `safety_object + info_marker` only → **INFORMATIONAL**: explain what the
  check does, with evidence.
- **A refusal returns** `dangerous:true`, `refused_as_fix:true`, `message`, `why_dangerous`,
  `safe_path` (read the actual pre-arm message and fix that cause; reproduce in SITL first), and only
  citations that explain the *purpose* of the check. Excerpts containing the disabling recipe are
  filtered out; if nothing safe remains, `citations: []` + `citations_note`.
- **`Props off for bench tests. SITL before hardware.`** is attached only when the safety gate fired
  or the topic is a bench/hardware procedure — not as decoration on every answer.
- **Verified**: 20 bypass phrasings (Vietnamese with and without diacritics, mixed, English) →
  **0 false negatives**; 10 benign information questions → **0 false positives**; blackbox run2 E
  section **15/15 pass** (run1 had 3 false negatives).

What it will never say: `ARMING_CHECK=0`, `ARMING_SKIPCHK≠0`, "force arm", "disable the failsafe /
fence", or a bench step without props-off + SITL.

---

## 9. How retrieval works

1. **Normalise + expand.** Query text is folded (case, diacritics) and expanded with a Vietnamese ↔
   English glossary matched **per token** (`bit` matches the word "bit", never the substring in
   "bitcoin"), stopwords removed.
2. **Corpus-anchor gate.** A query whose content words are absent from the index vocabulary (a word
   must appear in ≥ 3 documents, or be a `snake_case` symbol present at all) returns
   `found:false` + an out-of-scope note instead of plausible-looking hits.
3. **Hybrid candidate search.** SQLite **FTS5** over a distilled text field (path words + heading path
   + de-markup'd body) plus a literal identifier pass for exact symbol/parameter names, BM25 ranked.
4. **Document-level scoring.** Best chunk per document wins; boosts for path-token and heading-token
   matches, a bonus when the heading contains every query token; a penalty for simulator-only models
   under `libraries/SITL/` (a simulation model is not evidence of flight behaviour).
5. **Scope notes + confidence.** Out-of-corpus product names (`PX4`, …), version numbers that no
   pinned source carries, and weak overlap with the top-3 results each produce a `scope_notes` entry
   and lower `confidence` — never a fabricated version or a confident wrong answer.
6. **Citation.** Only then is a chunk turned into a citation (content hash, pinned URL, exact lines,
   600-char excerpt).

`chunks.text` stays byte-verbatim for citations; `chunks.distilled` exists only for the FTS index,
which is why markup-heavy wiki pages still match prose queries without corrupting the quote.

---

## 10. Configuration

Everything is environment-driven; no paths are hardcoded in `src/` beyond defaults.

| Variable | Default | Meaning |
|---|---|---|
| `ARM_REPO_ROOT` | the checkout containing `src/` | where `sources.yaml`, `glossary.vi-en.yaml`, `scope.yaml` live |
| `ARM_DATA_DIR` | `<repo>/data` | where `index.sqlite`, `corpus/` and `local/` live |
| `GOVERNOR_HOME` | `<repo>/research` | where the quota ledger (`ledger.sqlite`) lives |

Because the index and the ledger are resolved from these, you can keep **several isolated copies**
(e.g. one per branch/worktree) on the same machine; each points at its own `data/`, nothing is shared:

```powershell
$env:ARM_REPO_ROOT = "D:\work\ardupilot-research-mcp"
$env:ARM_DATA_DIR  = "D:\work\ardupilot-research-mcp\data"
$env:GOVERNOR_HOME = "D:\work\ardupilot-research-mcp\research"
```

The server needs `data/index.sqlite` and nothing else at serve time. If it is missing, every tool
answers `{"found":false,"error":"index not built: run ardupilot-research-ingest --all"}`.

---

## 11. Quota governance

Any metered source (Firecrawl / Exa / web search / GitHub API) is spent only through
`research/governor.py`, in a strict **reserve → call → record** loop, with a SQLite WAL ledger
(`research/ledger.sqlite`), a file lock, a sliding window, 20 % headroom, a minimum interval between
calls, a per-provider budget, cache-first reuse, `Retry-After` handling, exponential backoff, a
circuit breaker, and a `STATE.md` written when the budget is exhausted.

```powershell
python -m research.governor status
python -m research.governor reserve --provider firecrawl --endpoint scrape --query "https://…"
python -m research.governor record  --id 42 --status ok --http-code 200 --result-sha abc123
python -m research.governor export-report
```

Ledger for the build of this index: `calls=88, cost_units=32.0` — of which **firecrawl 0, exa 0,
web_search 0**; the corpus came from `git ls-remote` + codeload archives that cost no search units.
Building or serving the index from a warm cache costs **zero** quota.

---

## 12. Register it in a client

The server command is always:

```
python -m ardupilot_research_mcp.server      # stdio; needs PYTHONPATH=<repo>/src or an editable install
```

Replace `D:\Skill_tulan\ardupilot-research-mcp` with your checkout path in every snippet.

> **Status of these registrations: the config shapes are transcribed from each project's own
> documentation, but none was launched in a real client session in this environment — a sandbox
> blocked stdio pipes (`PermissionError: [WinError 5]` at process spawn). Treat "working" as
> UNVERIFIED until you see a tool call succeed.** `docs/client-setup.md` has the step-by-step
> PowerShell checklist to prove it locally.

### Claude Code

```powershell
claude mcp add --scope project ardupilot-research `
  --env PYTHONPATH=D:\Skill_tulan\ardupilot-research-mcp\src `
  --env ARM_REPO_ROOT=D:\Skill_tulan\ardupilot-research-mcp `
  --env ARM_DATA_DIR=D:\Skill_tulan\ardupilot-research-mcp\data `
  -- python -m ardupilot_research_mcp.server
claude mcp list                     # expect: ardupilot-research  connected
```

The generated project file (`.mcp.json`) looks like:

```json
{
  "mcpServers": {
    "ardupilot-research": {
      "type": "stdio",
      "command": "python",
      "args": ["-m", "ardupilot_research_mcp.server"],
      "env": {
        "PYTHONPATH": "D:\\Skill_tulan\\ardupilot-research-mcp\\src",
        "ARM_REPO_ROOT": "D:\\Skill_tulan\\ardupilot-research-mcp",
        "ARM_DATA_DIR": "D:\\Skill_tulan\\ardupilot-research-mcp\\data"
      }
    }
  }
}
```

### OpenCode

`opencode.jsonc` — local servers take an `mcp` entry with `type: "local"` and a command **array**
(source: `sst/opencode`, `packages/web/src/content/docs/mcp-servers.mdx`):

```jsonc
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "ardupilot-research": {
      "type": "local",
      "command": ["python", "-m", "ardupilot_research_mcp.server"],
      "enabled": true,
      "environment": {
        "PYTHONPATH": "D:\\Skill_tulan\\ardupilot-research-mcp\\src",
        "ARM_DATA_DIR": "D:\\Skill_tulan\\ardupilot-research-mcp\\data"
      }
    }
  }
}
```

### Codex

```toml
# ~/.codex/config.toml — verify the key names against your installed version: UNVERIFIED here
[mcp_servers.ardupilot-research]
command = "python"
args = ["-m", "ardupilot_research_mcp.server"]
env = { PYTHONPATH = 'D:\Skill_tulan\ardupilot-research-mcp\src', ARM_DATA_DIR = 'D:\Skill_tulan\ardupilot-research-mcp\data' }
```

### Proving it works (2 minutes)

```powershell
cd D:\Skill_tulan\ardupilot-research-mcp
$env:PYTHONPATH = "src"
python -m pytest -q                                   # 133 passed
python scripts\smoke_stdio.py                         # real MCP handshake + tool calls (run outside a sandbox)
```

Then in the client ask: *"Look up RC_OPTIONS and tell me which bit enables the ELRS 420kbaud mode."*
A correct answer cites `libraries/RC_Channel/RC_Channels_VarInfo.h`, lines 92–97, and names
`bit 13 — Use 420kbaud for ELRS protocol`. A wrong answer has no `cite_id`, or points at
`AP_Arming`. If the client reports the server as `failed`, `docs/client-setup.md` §4 walks through
python-on-PATH, `PYTHONPATH`, cwd, env and the `cmd /c` wrapper on Windows.

---

## 13. Tests and gates

```powershell
python -m pytest -q                                     # 133 passed
python scripts\check_traceability.py                    # requirement → test → result, failing=0
python scripts\fidelity_scan.py                         # 86 262 chunks, 0 mismatch, PASS
python scripts\check_param_citations.py                 # 5 089 params, 0 citation violations
python -m research.verify_citations                     # line ranges + pinned URLs, PASS
python -m research.audit_safety                         # the 6 required safety inputs
python -m research.eval_retrieval --set tests/golden.yaml --aggregate-only
python -m research.eval_retrieval --set tests/heldout_v3.yaml --aggregate-only
python scripts\mutation_check.py                        # mutation score
```

Last measured on the merged tree (`master`, index rebuilt from scratch):

| Gate | Result |
|---|---|
| `pytest -q` | **133 passed**, 0 failed, 0 skipped |
| `fidelity_scan.py` | **86 262 chunks, 0 mismatch — PASS** |
| `check_param_citations.py` | **5 089 checked, 0 violations** |
| `check_traceability.py` | 22 requirements, **failing=0** |
| `verify_citations` | PASS, **0 unpinned URLs** |
| safety corpus (30 cases) | **FN = 0, FP = 0** |
| golden set (dev, tunable) | recall@5 **1.000**, P@1 **0.767**, MRR **0.859** |
| held-out v3 (blind, frozen) | recall@5 **0.933**, P@1 **0.833**, MRR **0.868** |
| mutation score | **0.917** (11/12 applicable mutants killed; 3 stale mutants, 1 survivor documented) |
| blackbox run2 (108 frozen cases) | **92 pass / 16 fail**, 0 regressions vs run1 (80 pass) |

`tests/conftest.py` resets the in-process rate guard between tests (the guard itself still enforces
60 calls/min in production).

---

## 14. Measured quality

### Retrieval

| Set | What it is | recall@5 | precision@1 | MRR |
|---|---|---|---|---|
| `tests/golden.yaml` | 30 dev questions, **tunable** — not evidence | 1.000 | 0.767 | 0.859 |
| `tests/heldout_v3.yaml` | 30 blind, unambiguous questions, SHA-256 frozen before the run | **0.933** | **0.833** | **0.868** |
| `tests/heldout_locked.yaml` | first frozen set; several expectations are factually wrong (documented) | 0.433 | 0.300 | 0.334 |
| `tests/heldout_v2.yaml` | blind but ambiguous | 0.733 | 0.400 | 0.513 |

The fair instrument is v3 (`docs/eval-heldout-v3.md`); v1/v2 are kept for honesty, not for scoring.
Hashes live in `docs/heldout*.sha256`; the evaluator refuses to run if a set changed.

### Blackbox acceptance run

An independent tester froze 108 tool-level cases (`tests/blackbox_cases.md`, SHA-256
`1b53e69…dcaf27`), ran them over a real stdio session, and wrote `docs/blackbox/REPORT.md`
(run1: **80 pass / 28 fail**). After the fix round documented in `docs/FIX_REPORT.md`, the same
frozen cases were run **once** more into `docs/blackbox/run2/`:

- **92 pass / 16 fail**, **0 regressions** (no case went pass → fail), 12 cases fixed.
- Remaining 16 = **6 tool defects** (4 retrieval-ranking cases kept as known limitations + 2
  parameters whose macro default cannot be resolved) and **10 cases whose frozen expectation was
  wrong** (typo'd hex, non-existent parameter name, expectations that name a `source_id` as if it
  were a path).
- Detailed 108-row comparison + raw output: `docs/blackbox/run2/comparison.md`.

### Mutation testing

Hand-written semantic mutants against the shared code paths; the score is the share of applicable
mutants that some test kills. Latest run on the merged tree (`docs/mutation-report.md`):

```
selected mutants: 12   killed: 11   survived: 1   errors: 3   score: 0.917   (target 0.90)
survivor: M14 (stopword filter removed)
errors:   M06 / M11 / M12 — "mutation target not found" (their code was rewritten by the fix round)
```

The score is ≥ 0.90 on the mutants that still apply, and the two weak spots are written down instead
of hidden: the surviving mutant (deleting the stopword filter is not caught — a test would have to
assert on a noise query) and the three stale mutants that need re-pointing at the current code.

---

## 15. Reproduce the whole build

```powershell
# from a clean clone
python -m venv .venv; .\.venv\Scripts\Activate.ps1; pip install -e .
python -m research.fetch tags
python -m research.fetch download
python -m ardupilot_research_mcp.ingest.cli --all --rebuild-index   # `research.extract` runs inside this path
python -m research.build_params
python -m research.build_mavlink
python -m pytest -q
python scripts\check_traceability.py
python scripts\fidelity_scan.py
python scripts\check_param_citations.py
python -m research.eval_retrieval --set tests/heldout_v3.yaml --aggregate-only
python scripts\smoke_stdio.py
```

Known snag: `python -m research.extract` (the explicit form) exits **1** on the `local-project`
source because it has no tarball by design — the 7 pinned sources are extracted first, and
`ingest --all` skips `local-project` with a message. Use the `ingest --all --rebuild-index` line above
or pass `--source <id>` if you want the standalone extractor.

---

## 16. Layout

```
sources.yaml                     pinned corpus: repo, ref, tier, license, include/exclude globs
glossary.vi-en.yaml              Vietnamese ↔ English query terms (matched per token)
scope.yaml                       out-of-corpus product names, weak-match threshold
pyproject.toml                   mcp==1.30.0 + pyyaml; console scripts
src/ardupilot_research_mcp/
  server.py                      MCP wiring only (stdio, ToolAnnotations, 14 tools)
  config.py                      repo/data/ledger paths (ARM_REPO_ROOT, ARM_DATA_DIR)
  db.py                          SQLite schema + FTS5 external-content index
  query.py                       anchor gate, BM25 + identifier search, scope notes, ranking
  cite.py                        cite_id (content hash), pinned URLs, 600-char excerpts
  safety.py / safety_rules.yaml  bilingual refuse/inform gate, purpose-only citations
  guard.py                       per-process rate limit + response cap
  tools/<name>.py                one pure read-only tool per module
  decoders/                      CRSF frames, Intel HEX (stdlib, deterministic)
  ingest/                        the only package allowed to touch the network
research/                        fetch, extract, build_params, build_mavlink, governor, audits, eval
scripts/                         smoke_stdio, tool_matrix, fidelity_scan, checks, mutation, blackbox
examples/                        4 complete runnable scripts, each with its cite_ids
tests/                           unit, protocol, safety, offline, golden, frozen held-out sets
docs/                            design, licenses, eval reports, FIX_REPORT, client-setup, blackbox
```

`data/` (corpus + index + your `local-project` files) and `research/cache/` are **gitignored** — the
repo ships the recipe, not gigabytes of upstream source.

---

## 17. Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `index not built: run ardupilot-research-ingest --all` | `data/index.sqlite` missing → build it (§3.2) |
| `lookup_param` returns `found:false` for a real parameter | its library is outside the include list, or the name is from another vehicle; the payload lists real candidates and, when the release notes record it, a `renamed_hint` |
| `default: null` with `default_raw` set | the macro chain could not be resolved unambiguously — by design, it is not guessed (`default_resolved:false`) |
| `found:false` + "no anchor in the indexed corpus" | the corpus really does not use those words (out of scope); nothing was invented |
| `hex string too long` / `query too long (max N chars)` | input limits: query 2000, names 128, paths 1024, Intel HEX line 600, CRSF hex 4096 |
| `internal error` + `error_id` | a bug; the traceback is on **stderr** under that id — capture stderr and file it |
| `smoke_stdio.py` → `PermissionError: [WinError 5]` | the sandbox/session blocks stdio pipes; run it unsandboxed |
| `git: schannel: SEC_E_NO_CREDENTIALS` on Windows | `git -c http.sslBackend=openssl -c http.sslVerify=false …` |
| Client shows the server as `failed` with no reason | see `docs/client-setup.md` §4: python on PATH, `PYTHONPATH`, cwd, env vars, `cmd /c` wrapper |
| Held-out score looks low | read `docs/eval-heldout.md` / `-v2`: those sets are documented as unfair/ambiguous; v3 is the fair one |

---

## 18. Known limitations and unverified claims

**Unverified here (do not treat as working):**

- **Client registration** in a real OpenCode / Claude Code / Codex session — config shapes only.
  A sandbox blocked process spawn with pipes, so the failure could not be reproduced end-to-end.
- **Codex stdio key names** — its config reference redirects to a login page; nothing guessed.

**Known limitations (by design or out of scope):**

- **Retrieval ranking** still misses 4 frozen blackbox cases (`C1`, `C4`, `C10`, `C11`): the right
  file is indexed but not in the top-5 for those phrasings. Ranking was deliberately not tuned to
  individual questions.
- **Two parameters** (`SERIAL1_PROTOCOL`, `LOG_BITMASK`) are found but their default stays
  unresolved (macro chain), so a case that demands a numeric default for them still fails.
- **509 unresolved `@Param` blocks** and **142 unlinked blocks** — listed in
  `docs/fix/A-unresolved.txt`, not invented.
- **`A4_100K`** returns a schema-level validation error (`isError`, empty content) instead of a
  `{found:false}` payload, because `decode_crsf_frame` uses a pydantic `max_length` while the other
  tools validate in the wrapper. Both are explicit errors; the shapes differ.
- **`board_info`** follows one level of `include` in `hwdef.dat`.
- **T2 issue/PR evidence and T3 forum evidence** are not ingested (source list is the 7 pinned repos).
- **`local-project`** indexes your own files but has no pin and no URL — excluded from every recall
  number by construction.
- **`heldout_locked`** (0.433) stays below the 0.8 bar; that set is documented as unfair and is not
  used as evidence.
- `python -m research.extract` exits 1 on the tarball-less `local-project` source (§15).
- No `LICENSE` file yet — the license is declared as MIT in `pyproject.toml`; add the file before
  publishing if MIT is what you want.

---

## 19. Licenses and provenance

- **This server's code**: MIT (declared in `pyproject.toml`; add a `LICENSE` file before publishing).
- **Corpus**: not redistributed. `data/` and `research/cache/` are gitignored; the repo contains the
  recipe and the pins. Returned excerpts are capped at 600 characters, carry the source license and
  the pinned URL, so each quote stays traceable to its upstream file.
- **Per source** (read from each archive's own license file — `docs/license-notes.md`): ardupilot
  GPL-3.0 · ardupilot_wiki CC-BY-SA-3.0 · ExpressLRS GPL-3.0 · ExpressLRS Docs GPL-3.0 · EdgeTX
  GPL-2.0 · CRSF spec CC-BY-SA-4.0 · MAVLink XML **unstated** (kept labeled `unstated` by explicit
  user decision, not silently relicensed).
- Excluded file types (binaries, images, fonts, archives, `.hex`, `.apj`, …) never enter the corpus;
  every source's `LICENSE`/`COPYING`/`README` is force-included so provenance travels with the text.

---

## 20. Status and changelog

**v0.1.0 — first complete pass, 2026-10-25.**

- 14 tools over stdio, read-only, offline; 133 tests; 86 262 chunks with 0 fidelity mismatches.
- Parameter table rebuilt from the pinned `@Param`/`@Group`/`@Default` metadata:
  **230 → 5 089 parameters**, citation-to-own-block violations **3 891 → 0**, defaults
  **0 → 4 703 raw / 3 003 resolved**.
- Safety gate rewritten as data (`safety_rules.yaml`) with folded bilingual matching:
  **3/11 → 0/20** false negatives, **0/10** false positives, refusal citations free of disabling
  recipes.
- Input limits + internal-error shielding for every tool; token-based glossary; corpus-anchor gate so
  out-of-corpus questions return `found:false`; simulator-code ranking penalty.
- `decode_crsf_frame`: `frames_found`, `all_crc_valid:null` on zero frames, `truncated_tail_bytes`,
  C-style truncating µs (`tick 172 → 988`).
- Independent blackbox re-run over the frozen 108 cases: **92 pass, 0 regressions**.
- Full defect ledger, decisions and costs: **`docs/FIX_REPORT.md`**; per-defect logs in `docs/fix/`.

Open work that would move the needle next: rank the 4 remaining retrieval cases without
question-specific tuning, resolve more macro defaults, ingest T2/T3 evidence, and prove one real
client session end-to-end.
