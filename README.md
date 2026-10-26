# ardupilot-research-mcp

A local MCP server that answers ArduPilot, ExpressLRS, EdgeTX, CRSF and MAVLink questions from a
pinned offline corpus, and hands back a citation you can check with `git show`.

It runs on your machine as a stdio process. There is no URL, no port, no API key, no daemon and no
database server. Your MCP client starts `python -m ardupilot_research_mcp.server` and talks to it
over stdio. At answer time the server reads one file, `data/index.sqlite`. The network is used once,
to build that index.

It never arms, flashes, erases, writes parameters, opens a serial port or talks to a vehicle. Answers
either carry a `cite_id`, a pinned permalink, an exact line range and a verbatim excerpt, or say
`found:false`.

```
python -m ardupilot_research_mcp.server     # stdio MCP server, 14 tools
python -m pytest -q                         # 221 passed
```

Repo: `github.com/TOKGS/Drone_MCP`. Package `ardupilot-research-mcp` v0.1.0, Python 3.10 or newer.
Bản tiếng Việt: [`README.vi.md`](README.vi.md).

## What it is, and what it is not

It is a reference tool for someone writing or debugging ArduPilot code, wiring a flight controller,
decoding a CRSF frame, reading a `hwdef.dat`, checking an Intel HEX file, or asking why a parameter
no longer exists at a release tag. The corpus is the firmware source, wiki, MAVLink XML, ExpressLRS
source and docs, EdgeTX and the CRSF spec, each at a pinned ref.

It has no write path. No tool changes state, and an unanswered question returns `found:false` instead
of a guess.

| You ask | You get |
|---|---|
| `lookup_param("RC_OPTIONS")` | the declaring `@Param` block, its `@Bitmask` bits, `default_raw` and the resolved `default` (32), plus a pinned permalink |
| `decode_bitmask("RC_OPTIONS", "0x2000")` | `bit 13 SET: Use 420kbaud for ELRS protocol`, read from the pinned header |
| `mavlink_message("HEARTBEAT")` | msgid 0, fields, CRC extra, and a citation into `common.xml` |
| `decode_crsf_frame("C8 18 16 …")` | 16 channels of 11 bits, CRC8 status, microseconds from the spec macro `TICKS_TO_US`, truncated tail bytes |
| `check_intelhex_line(":1001…40")` | checksum status, record type, data bytes |
| `troubleshoot("tắt failsafe để nó khỏi báo")` | a refusal with the reason it is dangerous and a safe path, never the recipe for turning the failsafe off |
| `search_docs("giá bitcoin hôm nay")` | `found:false` with an out-of-scope note |

## Guarantees

| Guarantee | Enforced by |
|---|---|
| Read-only: all 14 tools carry `readOnlyHint=true, idempotentHint=true, openWorldHint=false` | `server.py`, `tests/test_offline.py` |
| Offline while answering: only `data/index.sqlite` is read, and no network module is imported outside `ingest/` | `tests/test_distil.py` (corpus deleted, tools still answer), `tests/test_offline.py` |
| Excerpts are real: chunk text is a byte slice of the pinned file, checked over all 86 262 chunks | `scripts/fidelity_scan.py`, `research/audit_git.py` |
| Pins, never branches: URLs point at a tag or a full commit SHA | `research/verify_citations.py` (0 unpinned URLs) |
| No invented names: a missing parameter, board or message returns `found:false` with real candidates, and a documented rename returns `renamed_hint` | `tests/test_params.py`, `tests/test_mavlink_board.py` |
| Safety first: requests to disable or mask arm checks, failsafes or fences are refused with a safe path, and hardware procedures carry `Props off for bench tests. SITL before hardware.` | `safety.py`, `safety_rules.yaml`, `tests/safety_cases_v2.yaml` |
| Excerpts are data: every citation is `untrusted: true` and is never followed as an instruction | `cite.py` |
| No silent failure: oversized input returns a `max_length` error, and an unexpected exception returns `{"found":false,"error":"internal error","error_id":"…"}` with details on stderr only | `tools/_base.py`, `tests/test_query.py` |

## Install

Requirements:

- Python 3.10 or newer with `pip` (tested on 3.11.9).
- About 3 GB free disk for the build: corpus 115 MB, `data/index.sqlite` 182 MB, and a 2.7 GB
  download cache. The cache is gitignored and can be deleted once the build succeeds, because the
  answering side needs only the index.
- Network once, for the build.

```powershell
git clone https://github.com/TOKGS/Drone_MCP.git ardupilot-research-mcp
cd ardupilot-research-mcp
python -m venv .venv; .\.venv\Scripts\Activate.ps1
pip install -e .
```

```bash
# Linux or WSL
python3 -m venv .venv && . .venv/bin/activate && pip install -e .
```

The only dependencies are `mcp==1.30.0` and `pyyaml`. `pytest` comes with the dev extra. The SDK is
pinned because the tool schema surface was verified against that exact version
(`docs/research-notes.md`).

## Build the index

```powershell
python -m research.fetch tags        # resolve the newest Copter-X.Y.Z tag with git ls-remote, no beta or rc
python -m research.fetch download    # download the pinned archives, no search quota
python -m research.extract           # filtered corpus into data/corpus
python -m ardupilot_research_mcp.ingest.cli --all --rebuild-index
python -m research.build_params      # @Param, @Bitmask and @Default into the params table
python -m research.build_mavlink     # MAVLink XML into message and enum tables
python -m ardupilot_research_mcp.ingest.cli --verify
# optional, semantic retrieval only: python -m research.build_vectors   (about 68 minutes)
```

Expect about five minutes and a 182 MB `data/index.sqlite`: 7 356 documents become 86 262 chunks,
5 089 parameters, 397 MAVLink messages and 2 367 enum entries.
The optional vector stage adds 63 MB and about an hour of CPU; everything else works without it.

`--resume` is the default and skips files already indexed by hash. `--rebuild-index` recreates the
SQLite file.

## Run it

```powershell
python -m ardupilot_research_mcp.server     # Ctrl+C to stop, nothing listens on a port
```

Because it speaks stdio, it prints nothing and waits for an MCP client. To try a tool without a
client:

```powershell
$env:PYTHONPATH = "src"
python -c "import sys; sys.path.insert(0,'src'); from ardupilot_research_mcp.tools.lookup_param import lookup_param; import json; print(json.dumps(lookup_param('RC_OPTIONS'), ensure_ascii=False, indent=1)[:1500])"
```

Good first questions:

```
lookup_param("ARMING_SKIPCHK")
decode_bitmask("RC_OPTIONS", "0x2000")
decode_crsf_frame("C81816E0031FF8C0073EF0810F7CE0031FF8C0073EF0810F7CAD")
check_intelhex_line(":10010000214601360121470136007EFE09D2190140")
troubleshoot("what does FS_THR_ENABLE do, and which value means disabled?")
```

## The 14 tools

Each tool is a pure function in `src/ardupilot_research_mcp/tools/<name>.py`. A shared guard limits
calls to 60 per minute, rejects oversized input before SQLite is touched, caps the response at three
excerpts per source, 600 characters per excerpt and 24 KB total, and turns unexpected exceptions into
an `internal error` payload with an `error_id`.

| Tool | Arguments | Returns |
|---|---|---|
| `search_docs` | `query` (max 2000), `scope` (`all`, `docs`, `code`, `protocol`, `dev`, `local`), `version`, `tier_max`, `limit` | ranked documents with citations, `scope_notes`, `confidence`, `note` |
| `get_chunk` | `cite_id`, `context_lines` | the chunk and its neighbours, with the same citation object |
| `lookup_param` | `name_or_pattern`, `vehicle` (default ArduCopter), `version` | `params[]` with `display_name`, `enum_values`, `bitmask`, `default_raw`, `default`, `default_resolved`, `renamed_hint`, citation |
| `decode_bitmask` | `param`, `value` as a number or bit names | bits to names, or names to a value, cross-checked against `@Bitmask` |
| `find_source` | `symbol_or_file`, `repo`, `version` | defining path, pinned permalink, citation |
| `board_info` | `board_name`, `hal` | parsed `hwdef.dat` facts: MCU, `SERIAL_ORDER`, RC defines, DMA hints, `included_files` |
| `mavlink_message` | `name_or_id` (`HEARTBEAT`, `0`, or an enum entry) | fields, CRC extra, enum values, citation into `common.xml` |
| `troubleshoot` | `symptom`, `context` | evidence-backed triage, or a refusal with `dangerous`, `refused_as_fix`, `message`, `safe_path`, `why_dangerous` |
| `get_script` | `topic` | a complete script from `examples/`, its `cite_ids` and run commands |
| `decode_crsf_frame` | `hex` (max 4096 characters) | frames, `frames_found`, `all_crc_valid` (`null` when there are no frames), microseconds per channel, `truncated_tail_bytes` |
| `check_intelhex_line` | `line` (max 600) | start code, byte count, checksum status, record type |
| `parse_ihex_summary` | `path` inside `data/` (max 1024) | record counts by type, data bytes, address span, EOF presence |
| `list_sources` | none | each source with pin, tier, license and document count |
| `index_status` | none | counts for sources, documents, chunks and params, index size, last ingest, offline note |

`scope` values: `docs` is the wiki plus ExpressLRS docs, `code` is firmware source, `protocol` is
MAVLink and CRSF, `dev` is the ArduPilot dev wiki, `local` is your own board files and never appears
in recall numbers, `all` is everything except `local`.

## Citation contract

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
  "excerpt": "…verbatim slice, 600 characters at most…",
  "version": "Copter-4.7.2 (2026-10-20)",
  "ingested_at": "2026-10-25T20:13:33+0700",
  "tier": "T1",
  "license": "GPL-3.0",
  "untrusted": true
}
```

`cite_id` comes from content: `sha256(source_id | path | line_start | line_end | sha256(text))`
truncated to 16 hex characters. Re-ingesting the same text yields the same id, and changing the text
changes the id.

`get_chunk(cite_id)` returns the text the citation promised. The blackbox run checked 20 of 20 with
`field_diff = 0`.

A tag pin gives `channel:"stable"`. A commit pin gives `channel:"snapshot"` with `unreleased:true`.
The local overlay gives `channel:"local"`, `pinned:false` and `url:null`.

## Corpus and pins

`sources.yaml` holds repo, ref (a tag or a SHA, never a branch), tier, license and include globs.
`research.fetch tags` resolves the newest `Copter-X.Y.Z` tag with `git ls-remote --tags --refs` and
drops beta and rc, and no release number is hardcoded in `src/`
(`tests/test_offline.py::test_no_hardcoded_release_version_outside_tests`).

| Source | Repo | Pin | Tier | License |
|---|---|---|---|---|
| `ardupilot` | ArduPilot/ardupilot | `Copter-4.7.2` at `fb77356789…` | T1 | GPL-3.0 |
| `ardupilot_wiki` | ArduPilot/ardupilot_wiki | `828de1f225dace34b482e63abaab15d25b2b1732` | T1 | CC-BY-SA-3.0 |
| `mavlink` | mavlink/mavlink | `eec8824212c1fe8c5d8f5181fcfdef54ee219b63` | T1 | unstated |
| `expresslrs` | ExpressLRS/ExpressLRS | `4.1.0` at `a9d4a9cb5b5687c4c9d7e9e7fbdf44ad93651da6` | T2 | GPL-3.0 |
| `expresslrs_docs` | ExpressLRS/ExpressLRS | `5ed656b6ebc7a38b6012297cf40fe5bc87232bed` | T2 | GPL-3.0 |
| `edgetx` | EdgeTX/edgetx | `v2.12.5` at `0ebe2e98b2085e2251ad6773b26c8a7ab8dd3e99` | T2 | GPL-2.0 |
| `crsf_spec` | CRSF spec mirror | `a73f7dc5386e5b8744aa4a23b3af5354ee0d4c92` | T2 | CC-BY-SA-4.0 |
| `local-project` | your files | `local` | T3 | user-owned |

The index holds 7 sources, 7 356 documents and 86 262 chunks in 182.3 MB. `list_sources` gives the
per-source counts. Licenses were read from each archive's own license file
(`docs/license-notes.md`). The corpus is never committed: `data/` and `research/cache/` are
gitignored.

## The ArduPilot 4.6 variant

A drone on 4.6 firmware gets wrong declarations from the 4.7 pin: `ARMING_CHECK` is
`found:false` there because 4.7 renamed it to `ARMING_SKIPCHK`, and `ATC_ACCEL_*` became
`ATC_ACC_*`. `sources-4.6.yaml` pins `Copter-4.6.2` instead and builds into `data/4.6`
(169.0 MB index, 79 558 chunks, 4 356 parameters, `verify: PASS`, heldout_v3 recall@5 0.933).
Select it with `ARM_SOURCES` and `ARM_DATA_DIR`; `.mcp.json.example` carries the second server
entry. Build steps, measured timings and what is not verified for this variant:
[docs/variant-4.6.md](docs/variant-4.6.md).

## Parameters

`lookup_param` answers from the `@Param`, `@Bitmask` and `@Default` metadata in the pinned source.

- 5 089 parameter names from 2 070 `@Param` blocks. Full names are resolved through the pinned
  `@Group` and `@Path` chain, so `@Param: 1_PROTOCOL` in `AP_SerialManager.cpp` plus the `SERIAL`
  prefix becomes `SERIAL1_PROTOCOL`. Instance families expand: `RC1..RC16`, `SERIAL1..8`,
  `BATT` and `BATTA`, `INS`, `INS2`, `INS3`, `COMPASS2/3`, `OSD1..5`. No row is a duplicate: zero
  rows share `(path, line_start, prefix)`.
- `default_raw` is the verbatim `@Default:` argument, present on 4 703 of 5 089 rows. It becomes a
  number only when it is a literal, a bit expression, or exactly one in-corpus `#define`. That
  resolves 3 003 rows and leaves 1 700 unresolved, which is reported rather than guessed. Examples:
  `FS_THR_ENABLE` gives 1 from `FS_THR_ENABLED_ALWAYS_RTL`, `FS_THR_VALUE` gives 975, `RC_OPTIONS`
  gives 32, `ARMING_SKIPCHK` gives 0. `LOG_BITMASK` keeps `default_raw=DEFAULT_LOG_BITMASK` with
  `default_resolved:false`.
- Every citation points at the parameter's own block. All 5 089 rows are machine-checked so the
  excerpt contains `@Param:<suffix>` and the line range covers it, with zero violations
  (`scripts/check_param_citations.py`). Before this was fixed, 3 891 of 5 089 citations showed a
  neighbouring block.
- Renames are reported. `ARMING_CHECK` returns `found:false` with
  `renamed_hint{new:"ARMING_SKIPCHK", path:"ArduCopter/ReleaseNotes.txt"}`. `WPNAV_SPEED` returns
  `found:false` with no hint, because the release notes do not record that rename.
- Usage coverage is measured against real files. Of 1 440 unique names used by
  `Tools/autotest/default_params/*.param` and `Tools/Frame_params/*.param` at the pin, 739 (51.3 %)
  are found. Most of the rest belong to other vehicles' frames, classified in
  `docs/fix/A-names.txt`.
- Unresolvable cases are listed in `docs/fix/A-unresolved.txt`: 509 unresolved blocks and 142
  unlinked blocks.

## Safety policy

The server explains safety systems. It does not present disabling one as a fix.

The rules live in `src/ardupilot_research_mcp/safety_rules.yaml` as lists of `disable_verbs`,
`safety_objects`, `safety_params`, `value_patterns`, `info_markers`, `hardware_markers` and
`dangerous_excerpt`. Matching runs on folded text, so `tắt failsafe`, `tat failsafe` and `turn the
failsafe off` hit the same rule.

A request is refused when a disable verb targets a safety object, or when a safety parameter is
combined with a pattern that zeroes it, and that holds inside a question too. A safety object with
only an information marker takes the informational branch, which explains what the check does and
cites evidence.

A refusal returns `dangerous:true`, `refused_as_fix:true`, `message`, `why_dangerous` and
`safe_path`, where the safe path says to read the actual pre-arm message, fix that cause, and
reproduce in SITL first. Citations are limited to ones explaining the purpose of the check; excerpts
that carry the disabling recipe are filtered out, and when nothing safe remains the payload has
`citations: []` and a `citations_note`.

`Props off for bench tests. SITL before hardware.` appears when the gate fired or when the topic is a
bench procedure, and not otherwise.

Measured on the current tree: 20 bypass phrasings (Vietnamese with and without diacritics, mixed,
and English) give 0 false negatives, 10 benign information questions give 0 false positives, and the
blackbox run2 E section passes 15 of 15. Run1 missed three.

It will not print `ARMING_CHECK=0`, `ARMING_SKIPCHK≠0`, "force arm", "disable the failsafe or fence",
or a bench step without the props-off line.

## How retrieval works

The query is folded for case and diacritics and expanded with a Vietnamese to English glossary
matched per token, so `bit` matches the word and not the substring in `bitcoin`. Stopwords are
removed.

A corpus anchor gate follows. Content words that appear in fewer than three documents, and that are
not `snake_case` symbols present in the index, do not anchor a query, and an unanchored query returns
`found:false` with an out-of-scope note.

Candidates come from FTS5 over a distilled text field holding path words, the heading path and the
de-markuped body, plus a literal identifier pass for exact symbol and parameter names, ranked by
BM25.

Scoring is per document: the best chunk wins, with boosts for path and heading tokens, a bonus when
the heading carries every query token, and a penalty for simulator-only models under
`libraries/SITL/`.

Scope notes and confidence follow. Out-of-corpus product names such as `PX4`, version numbers no pin
carries, and weak overlap with the top three results each add a `scope_notes` entry and lower
`confidence`.

Only then does a chunk become a citation, with its content hash, pinned URL, line range and excerpt.
`chunks.text` stays byte-verbatim for citations, and `chunks.distilled` exists only for the FTS
index, which is why markup-heavy wiki pages match prose queries without corrupting the quote.

## Configuration

Six environment variables, with defaults filled in by the checkout:

| Variable | Default | Meaning |
|---|---|---|
| `ARM_REPO_ROOT` | the checkout containing `src/` | where `sources.yaml`, `glossary.vi-en.yaml` and `scope.yaml` live |
| `ARM_DATA_DIR` | `<repo>/data` | where `index.sqlite`, `corpus/` and `local/` live |
| `GOVERNOR_HOME` | `<repo>/research` | where the quota ledger lives |
| `ARM_SOURCES` | `<repo>/sources.yaml` | alternate pin set, for example `sources-4.6.yaml` |
| `ARM_DENSE` | unset, off | `1` enables the optional semantic rerank (see below) |
| `ARM_MODEL_DIR` | `<data>/models/multilingual-e5-small` | ONNX model and tokenizer directory |
| `ARM_DOC_PRIOR` | unset, off | `1` adds the per-document semantic prior on top of `ARM_DENSE=1`; measured worse on both dev sets, kept for reproduction |

Because the index and the ledger resolve from these, you can keep isolated copies on one machine,
for example one per worktree:

```powershell
$env:ARM_REPO_ROOT = "D:\work\ardupilot-research-mcp"
$env:ARM_DATA_DIR  = "D:\work\ardupilot-research-mcp\data"
$env:GOVERNOR_HOME = "D:\work\ardupilot-research-mcp\research"
```

A missing index makes every tool return
`{"found":false,"error":"index not built: run ardupilot-research-ingest --all"}`.

## Quota governance

Metered sources (Firecrawl, Exa, web search, the GitHub API) are spent only through
`research/governor.py`, in a reserve, call, record loop. The governor keeps a SQLite WAL ledger
(`research/ledger.sqlite`) with a file lock, a sliding window, 20 % headroom, a minimum interval
between calls, a per-provider budget, cache-first reuse, `Retry-After` handling, exponential backoff,
a circuit breaker, and a `STATE.md` written when the budget runs out.

```powershell
python -m research.governor status
python -m research.governor reserve --provider firecrawl --endpoint scrape --query "https://…"
python -m research.governor record  --id 42 --status ok --http-code 200 --result-sha abc123
python -m research.governor export-report
```

The ledger for this index reads `calls=88, cost_units=32.0`, with firecrawl 0, exa 0 and web_search
0. The corpus came from `git ls-remote` and codeload archives, which spend no search units. A rebuild
from a warm cache spends nothing.

## Register a client

The server command is always:

```
python -m ardupilot_research_mcp.server
```

It needs `PYTHONPATH=<repo>/src` or an editable install. Replace
`D:\Skill_tulan\ardupilot-research-mcp` with your checkout path.

What has been verified outside the sandbox: in Claude Code 2.1.308 the server connects, the client
lists all 14 tools as `mcp__ardupilot-research__*`, and `claude mcp list` reports `√ Connected` for a
user-scope registration. The Claude Code model turn stops at `"Not logged in · Please run /login"`,
which is client authentication and not the server.

In OpenCode 2.1.3 with the free model `opencode/deepseek-v4.1-flash-free` a full turn ran: the model
called `tools["ardupilot-research"].lookup_param({name_or_pattern:"RC_OPTIONS"})`, got
`default: 32` with `cite_id ardupilot#11fb2497e2a89d95`, and answered `32`. Transcript:
`docs/blackbox/h/opencode_stream.jsonl`; setup in `docs/client-setup.md` section 7.

Codex was not launched. Raw init JSON for both working clients is in `docs/client-setup.md`.

A project-scope `.mcp.json` needs one interactive approval. A headless `-p` session shows it as
`pending` with 0 tools, and that is what run1 recorded as `status: failed`. Setting
`enableAllProjectMcpServers: true` in `.claude/settings.json` or `.claude/settings.local.json` did not
change it on 2.1.308.

### Claude Code

```powershell
# user scope: Connected with no manual approval
claude mcp add --scope user ardupilot-research `
  --env PYTHONPATH=D:\Skill_tulan\ardupilot-research-mcp\src `
  --env ARM_REPO_ROOT=D:\Skill_tulan\ardupilot-research-mcp `
  --env ARM_DATA_DIR=D:\Skill_tulan\ardupilot-research-mcp\data `
  -- python -m ardupilot_research_mcp.server
claude mcp list                     # expect: ardupilot-research … √ Connected

# project scope: writes .mcp.json, then approve once in the TUI
claude mcp add --scope project ardupilot-research …            # then run `claude` and approve
# or skip approval by passing the file explicitly:
claude -p "<question>" --mcp-config .\.mcp.json --strict-mcp-config
```

The project file is per-machine, so it is gitignored; the committed template is
`.mcp.json.example`. It looks like this:

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

`opencode.jsonc`. Local servers take an `mcp` entry with `type: "local"` and a command array,
transcribed from `sst/opencode`, `packages/web/src/content/docs/mcp-servers.mdx`:

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

The key names below are unverified. Codex's config reference redirects to a login page, so nothing was
guessed:

```toml
[mcp_servers.ardupilot-research]
command = "python"
args = ["-m", "ardupilot_research_mcp.server"]
env = { PYTHONPATH = 'D:\Skill_tulan\ardupilot-research-mcp\src', ARM_DATA_DIR = 'D:\Skill_tulan\ardupilot-research-mcp\data' }
```

### Proving it works

```powershell
claude mcp list
# ardupilot-research: python -m ardupilot_research_mcp.server - √ Connected
claude -p "hi" --mcp-config .\.mcp.json --strict-mcp-config --output-format stream-json --verbose 2>&1 |
  Select-Object -First 1
# …"mcp_servers":[{"name":"ardupilot-research","status":"connected"}],
#  "tools":[… "mcp__ardupilot-research__lookup_param" … 14 of them]
```

Then ask: *"Look up RC_OPTIONS and tell me which bit enables the ELRS 420kbaud mode."* A correct
answer cites `libraries/RC_Channel/RC_Channels_VarInfo.h`, lines 92 to 97, and names
`bit 13: Use 420kbaud for ELRS protocol`. A wrong answer has no `cite_id`, or points at `AP_Arming`.
If the client reports the server as failed, `docs/client-setup.md` section 4 walks through python on
PATH, `PYTHONPATH`, cwd, environment variables and the `cmd /c` wrapper.

## Tests and gates

```powershell
python -m pytest -q                                     # 221 passed
python scripts\check_traceability.py                    # requirement to test to result, failing=0
python scripts\fidelity_scan.py                         # 86 262 chunks, 0 mismatch, PASS
python scripts\check_param_citations.py                 # 5 089 parameters, 0 violations
python scripts\check_readmes.py                         # both READMEs: no AI tells, numbers agree
python scripts\bench.py                                 # search p50/p95 against a budget
python -m research.verify_citations                     # line ranges and pinned URLs, PASS
python -m research.audit_safety                         # the six required safety inputs
python -m research.eval_retrieval --set tests/golden.yaml --aggregate-only
python -m research.eval_retrieval --set tests/heldout_v3.yaml --aggregate-only
python scripts\mutation_check.py                        # mutation score
```

Last measured on the merged tree with the index rebuilt from scratch:

| Gate | Result |
|---|---|
| `pytest -q` | 221 passed, 1 skipped |
| `fidelity_scan.py` | 86 262 chunks, 0 mismatch, PASS |
| `check_param_citations.py` | 5 089 checked, 0 violations |
| `check_traceability.py` | 22 requirements, failing=0 |
| `verify_citations` | PASS, 0 unpinned URLs |
| safety corpus, 30 cases | 0 false negatives, 0 false positives |
| golden set, dev and tunable | recall@5 1.000, P@1 0.767, MRR 0.859 |
| held-out v3, blind and frozen | recall@5 0.933, P@1 0.833, MRR 0.868 |
| mutation | 1.000, 14 scored mutants killed, 1 equivalent mutant excluded and flagged |
| blackbox, 108 frozen cases | run2 92 pass / 16 fail, run3 93 / 15 after the chunk fix, 0 regressions, 3 repeats byte-identical |
| scoring determinism | 5 scripts run twice, byte-identical output |
| `check_readmes.py` | PASS |
| `bench.py` | search p50 58.5 ms, p95 186 ms, budget 400 ms, PASS |

`tests/conftest.py` resets the in-process rate guard between tests. The guard still enforces 60 calls
per minute in production.

Both `data/index.sqlite` and `data/corpus` are gitignored, so a fresh clone adapts instead of
failing: modules that need the index or the corpus skip themselves. With both present the suite runs
221 passed and 1 skipped; the skip is the directory-symlink escape test on this Windows account.

## Measured quality

| Set | What it is | recall@5 | P@1 | MRR |
|---|---|---|---|---|
| `tests/golden.yaml` | 30 dev questions, tunable, not evidence | 1.000 | 0.767 | 0.859 |
| `tests/heldout_v3.yaml` | 30 blind questions with one defensible answer, SHA-256 frozen before the run | 0.933 | 0.833 | 0.868 |
| `tests/heldout_locked.yaml` | first frozen set, several expectations factually wrong | 0.433 | 0.300 | 0.334 |
| `tests/heldout_v2.yaml` | blind but ambiguous | 0.733 | 0.400 | 0.513 |

The fair instrument is v3 (`docs/eval-heldout-v3.md`). v1 and v2 are kept for honesty and are not used
for scoring. Hashes are in `docs/heldout*.sha256`, and the evaluator refuses to run if a set changed.

Eval set v4 is the current ruler: 125 questions written from corpus evidence, split into 53 dev and
72 frozen held-out questions (`docs/eval-v4.md`). Held-out results, one row per configuration:

| configuration | recall@5 | P@1 | MRR | chunk-hit@5 | negative-pass |
|---|---|---|---|---|---|
| Phase 1 baseline | 0.692 | 0.369 | 0.493 | 0.369 | 0.571 |
| Rung 1 lexical, the default | 0.723 | 0.323 | 0.475 | 0.369 | 0.571 |
| Rung 2 semantic rerank, opt-in | 0.692 | 0.277 | 0.439 | 0.354 | 0.571 |

The Vietnamese subset is the weak spot: 0.516 recall@5 against 0.906 for English in the default
build. Per category and per language: `docs/upgrade/rung1.md` and `docs/upgrade/rung2.md`.

An independent tester froze 108 tool-level cases (`tests/blackbox_cases.md`, SHA-256
`1b53e69…dcaf27`), ran them over one stdio session, and wrote `docs/blackbox/REPORT.md`, which scored
80 pass and 28 fail. After the fix round in `docs/FIX_REPORT.md` the same cases ran again into
`docs/blackbox/run2/`: 92 pass, 16 fail, 12 fixed, none going from pass to fail.

The chunk-picker change then fixed the last retrieval misquote, so the suite ran a third time, three
repeats in a row: 93 pass, 15 fail, still no regression, and all 110 payloads identical across the
repeats. `docs/blackbox/run3/comparison.md` has the tally and the 17 payloads that differ from run2.

The 15 remaining splits into 5 tool defects and 10 cases whose frozen expectation was wrong (a hex
string missing a nibble, parameters that do not exist at the tag, expectations that treat a
`source_id` as part of a path).

The five scoring scripts were also run twice on the same raw output and produced byte-identical
results, so the 92/16 verdict does not depend on run order or timing
(`docs/blackbox/run2/determinism.md`).

## Optional: semantic retrieval

An ONNX e5-small retriever can rerank the BM25 candidates. It is off by default: measured on the
frozen eval set v4 it did not beat the plain ranking (`docs/upgrade/rung2.md`).

```powershell
pip install -e ".[embeddings]"      # onnxruntime, tokenizers, numpy
python -m research.build_vectors    # 86 262 chunks, 63 MB, about 68 minutes on 8 cores
$env:ARM_DENSE = "1"                # opt in; unset means BM25 only
```

The model is `intfloat/multilingual-e5-small` (ONNX, 448.5 MB, MIT, see `docs/license-notes.md`),
expected under `data/models/multilingual-e5-small/`; point `ARM_MODEL_DIR` elsewhere if needed. The
index grows by 63 MB and the first search of a process spends about 7 s loading the vectors.

Measured tradeoff on held-out v4: recall@5 0.692 against 0.723 and MRR 0.439 against 0.475 for the
default ranking, so enable it only if your own questions look more semantic than identifier based.
Missing extras, model or `chunk_vectors` table always fall back to BM25; `ARM_DENSE=1` with missing
assets prints one warning naming the reason, and `index_status` reports
`dense: {state: "requested-but-unavailable", unavailable_reason: ...}`.

## Reproduce the build

```powershell
python -m venv .venv; .\.venv\Scripts\Activate.ps1; pip install -e .
python -m research.build_all --gates         # fetch, extract, ingest, params, mavlink, then the gates
python -m research.eval_retrieval --set tests/heldout_v3.yaml --aggregate-only
python scripts\smoke_stdio.py               # needs stdio pipes, so run it outside a sandbox
python -m research.build_all --prune-cache   # optional: delete the downloaded archives
```

`build_all` runs each stage as its own process and stops at the first failure, so the error names the
stage. `--dry-run` prints the commands without running them, and `--prune-cache` removes the 2.7 GB
of archives once the index exists.

## Layout

```
sources.yaml                     pinned corpus: repo, ref, tier, license, include and exclude globs
glossary.vi-en.yaml              Vietnamese to English query terms, matched per token
scope.yaml                       out-of-corpus product names, weak-match threshold
pyproject.toml                   mcp==1.30.0 and pyyaml, console scripts
src/ardupilot_research_mcp/
  server.py                      MCP wiring only: stdio, ToolAnnotations, 14 tools
  config.py                      repo, data and ledger paths
  db.py                          SQLite schema and FTS5 external-content index
  query.py                       anchor gate, BM25 and identifier search, scope notes, ranking
  cite.py                        cite_id, pinned URLs, 600-character excerpts
  safety.py                      refuse and inform gate
  safety_rules.yaml              the rules themselves
  guard.py                       rate limit and response cap
  tools/<name>.py                one pure read-only tool per module
  decoders/                      CRSF frames and Intel HEX, stdlib only
  ingest/                        the only package allowed to touch the network
research/                        fetch, extract, build_params, build_mavlink, governor, audits, eval
scripts/                         smoke, tool matrix, fidelity, checks, mutation, blackbox
examples/                        4 runnable scripts, each with its cite_ids
tests/                           unit, protocol, safety, offline, golden, frozen held-out sets
docs/                            design, licenses, eval reports, FIX_REPORT, client-setup, blackbox
```

`data/` holds the corpus, the index and your `local-project` files. Both it and `research/cache/` are
gitignored, so the repo ships the recipe rather than gigabytes of upstream source.

## Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `index not built: run ardupilot-research-ingest --all` | `data/index.sqlite` is missing, build it |
| `lookup_param` returns `found:false` for a real parameter | its library is outside the include list, or the name belongs to another vehicle; the payload lists real candidates and, when the release notes record it, a `renamed_hint` |
| `default: null` with `default_raw` set | the macro chain has no single resolution, so it is reported instead of guessed (`default_resolved:false`) |
| `found:false` with "no anchor in the indexed corpus" | the corpus does not use those words |
| `hex string too long` or `query too long (max N chars)` | input limits: query 2000, names 128, paths 1024, Intel HEX line 600, CRSF hex 4096 |
| `internal error` with an `error_id` | a bug; the traceback is on stderr under that id, capture stderr and report it |
| `smoke_stdio.py` raises `PermissionError: [WinError 5]` | the session blocks stdio pipes, run it outside the sandbox |
| `git: schannel: SEC_E_NO_CREDENTIALS` on Windows | `git -c http.sslBackend=openssl -c http.sslVerify=false …` |
| the client shows the server as failed with no reason | `docs/client-setup.md` section 4 covers python on PATH, `PYTHONPATH`, cwd, environment variables and `cmd /c`; also see the approval note above |
| a held-out score looks low | read `docs/eval-heldout.md` and `docs/eval-heldout-v2.md`; those two sets are documented as unfair or ambiguous |

## Limitations and unverified claims

Verified on Claude Code 2.1.308 outside the sandbox: the server connects, the client lists 14 tools,
and `claude mcp list` reports `√ Connected` for a user-scope registration.

Still unverified:

- Codex. It is not installed here and its stdio key names are unconfirmed.
- A model-issued tool call inside Claude Code, which needs a logged-in session. OpenCode has one on
  record (see above); the Claude Code client was not logged in.

Known limitations:

- Ranking misses 3 frozen blackbox cases (`C4`, `C10`, `C11`). The right file is indexed but does
  not reach the top five for those phrasings. `C1` is fixed: the winning chunk is now the definition
  (`0xD5`), not the Command-frame paragraph (`0xBA`) that shared its words.
- Two parameters, `SERIAL1_PROTOCOL` and `LOG_BITMASK`, are found but their default stays unresolved
  because the macro chain is not single-valued. A case that demands a numeric default for them fails.
- 509 unresolved `@Param` blocks and 142 unlinked blocks are listed in `docs/fix/A-unresolved.txt`.
- `A4_100K` returns a schema validation error (`isError`, empty content) rather than a
  `{found:false}` payload, because `decode_crsf_frame` uses a pydantic `max_length` while the other
  tools validate in the wrapper. Both are explicit errors, with different shapes.
- `board_info` follows one level of `include` in `hwdef.dat`.
- T2 issue and PR evidence and T3 forum evidence are not ingested. The source list is the seven
  pinned repos.
- `local-project` indexes your own files with no pin and no URL, and stays out of every recall number.
- `heldout_locked` scores 0.433, below the 0.8 bar. That set is documented as unfair and is not used
  as evidence.
- The link-escape test (`tests/test_hardening.py`) skips on accounts that cannot create
directory symlinks, so junction traversal is unproven on this machine.

## Licenses and provenance

The server code is MIT, in `LICENSE` (and declared in `pyproject.toml`).

The corpus is not redistributed. `data/` and `research/cache/` are gitignored, and returned excerpts
are capped at 600 characters, carry the source license and the pinned URL, so a quote stays traceable
to its upstream file.

Per source, read from each archive's own license file (`docs/license-notes.md`): ardupilot GPL-3.0,
ardupilot_wiki CC-BY-SA-3.0, ExpressLRS GPL-3.0, ExpressLRS Docs GPL-3.0, EdgeTX GPL-2.0, CRSF spec
CC-BY-SA-4.0, MAVLink XML unstated and kept with that label by explicit decision.

Binaries, images, fonts, archives, `.hex` and `.apj` files never enter the corpus, and every source's
`LICENSE`, `COPYING` or `README` is force-included so provenance travels with the text.

## Status

v0.1.0, first complete pass, 2026-10-25.

- 14 tools over stdio, read-only and offline, 221 tests, 86 262 chunks with no fidelity mismatch.
- Parameter table rebuilt from pinned metadata: 230 to 5 089 parameters, citation violations 3 891 to
  0, defaults 0 to 4 703 raw with 3 003 resolved.
- Safety gate rewritten as data with folded bilingual matching: false negatives went from 3 of 11 to
  0 of 20, false positives stayed at 0 of 10, and refusal citations no longer carry the disabling
  recipe.
- Input limits and internal-error shielding on every tool, a token-based glossary, a corpus anchor
  gate so out-of-corpus questions return `found:false`, and a ranking penalty for simulator code.
- `decode_crsf_frame` reports `frames_found`, returns `all_crc_valid:null` with zero frames, reports
  `truncated_tail_bytes`, and converts microseconds with C-style truncating division, so tick 172
  gives 988.
- Independent blackbox reruns over the frozen 108 cases: 92 pass at run2, 93 at run3, no regressions,
  and three repeats with identical payloads.
- Client wiring proven in two real clients: Claude Code connects and lists 14 tools (user scope
  reports `√ Connected`), and an OpenCode session with a free model issued a `lookup_param` call and
  answered from the citation.
- Chunk selection inside a winning document now prefers whole-word matches and the chunk without a
  narrower heading, which turns C1 from a near-miss into a correct quote.
- Mutation harness re-pointed at the current code, an equivalent mutant classified instead of scored,
  and the stopword filter is now covered by a test.
- `research.build_all` gives the build one entry point, `research.extract` no longer fails on the
  local overlay, and `scripts/bench.py` guards latency.
- CI runs the unit suite, the README gate and traceability on Windows and Ubuntu; a weekly job builds
  the index and runs the documented gates.
- `LICENSE` added, and `.mcp.json` is per-machine again (only `.mcp.json.example` is committed).

The defect ledger, decisions and costs are in `docs/FIX_REPORT.md`, with per-defect logs under
`docs/fix/`.

Next steps that would move the needle: rank the four remaining retrieval cases without tuning per
question, resolve more macro defaults, ingest T2 and T3 evidence, and finish one logged-in client
session so a model-issued tool call is on record.
