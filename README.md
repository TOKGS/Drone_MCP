# ardupilot-research-mcp

A local, **read-only, offline** MCP server (stdio) that answers ArduPilot development questions
with **machine-checkable citations**: every documentary answer carries a `cite_id`, a SHA-pinned
permalink, an exact line range and a verbatim excerpt.

It never arms, flashes, erases, writes parameters, opens a serial port or talks to a vehicle, and
it makes **no network calls at serve time**.

- 14 tools: `search_docs`, `get_chunk`, `lookup_param`, `decode_bitmask`, `find_source`,
  `board_info`, `mavlink_message`, `troubleshoot`, `get_script`, `decode_crsf_frame`,
  `check_intelhex_line`, `parse_ihex_summary`, `list_sources`, `index_status`
- Corpus: 7 pinned sources → 63 808 chunks → 214 params, 397 MAVLink messages, 2367 enum entries
- Stack: Python 3.10+, stdlib + `mcp==1.30.0` + `pyyaml` (nothing else)

## Honest status (read this before trusting it)

| Claim | Status |
|---|---|
| 100 % of excerpts match the Git blob at the cited lines | **verified**: 63 808 chunks, 0 mismatches |
| Out-of-corpus questions return `found:false` | **verified** |
| Safety gate refuses arming/failsafe bypasses | **verified** (6 required inputs) |
| Works offline from the index alone | **verified** (corpus deleted, tools still answer) |
| recall@5 ≥ 0.8 on a held-out set | **NOT MET**: 0.367 (v1) and 0.533 (blind v2) — see `docs/eval-heldout*.md` |
| Mutation coverage ≥ 90 % | **NOT RUN** |
| Registered in a real OpenCode / Claude Code / Codex session | **UNVERIFIED** (configs below are transcribed from each project's own repo; none was launched here) |

## Install

```powershell
# PowerShell
python -m venv .venv; .\.venv\Scripts\Activate.ps1
pip install -e .
```
```bash
# WSL / Linux
python3 -m venv .venv && . .venv/bin/activate
pip install -e .
```

## Build the index (the only phase that uses the network)

```powershell
python -m research.fetch tags          # resolve the newest Copter-X.Y.Z tag (git ls-remote / API)
python -m research.fetch download      # tarballs at the pinned refs (0 search quota)
python -m research.extract             # filtered corpus -> data/corpus
python -m ardupilot_research_mcp.ingest.cli --all
python -m research.build_params        # @Param metadata  -> params table
python -m research.build_mavlink       # MAVLink XML      -> message/enum tables
python -m ardupilot_research_mcp.ingest.cli --verify
```
```bash
# WSL / Linux: identical commands with python3.
```

`--rebuild-index` recreates `data/index.sqlite`; `--resume` (default) skips files whose hash is
already indexed, so a stopped build loses nothing.

## Register it in a client

Everything below is a stdio server whose command is the installed module. Replace
`C:\Skill_tulan\ardupilot-research-mcp` with your checkout path.

### OpenCode — **verified** against this project's own docs

Source: `sst/opencode`, `packages/web/src/content/docs/mcp-servers.mdx` (fetched 2026-10-25).
Local servers live under `mcp` with `type: "local"` and a `command` **array**:

```jsonc
// opencode.jsonc
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "ardupilot-research": {
      "type": "local",
      "command": ["python", "-m", "ardupilot_research_mcp.server"],
      "enabled": true,
      "environment": {
        "ARM_DATA_DIR": "C:\\Skill_tulan\\ardupilot-research-mcp\\data"
      }
    }
  }
}
```

### Claude Code — **partially verified**

Source: `anthropics/claude-code`, `plugins/plugin-dev/skills/mcp-integration/examples/stdio-server.json`
(fetched 2026-10-25): a `mcpServers` map whose entries take `command`, `args`, `env`.

```json
{
  "mcpServers": {
    "ardupilot-research": {
      "command": "python",
      "args": ["-m", "ardupilot_research_mcp.server"],
      "env": { "ARM_DATA_DIR": "C:\\Skill_tulan\\ardupilot-research-mcp\\data" }
    }
  }
}
```
The project-scoped file name (`.mcp.json` vs a settings file) is **UNVERIFIED** — check
`claude mcp add --help` in your installed version.

### Codex — **partially verified**

Source: `openai/codex` (fetched 2026-10-25) confirms `[mcp_servers.<name>]` tables, e.g.
`[mcp_servers.openaiDeveloperDocs] url = "https://developers.openai.com/mcp"`. The **stdio keys are
UNVERIFIED**: Codex keeps its config reference outside the repo and that URL redirects to a login
page (`learn.chatgpt.com`), so nothing was guessed here. Confirm the key names in
`~/.codex/config.toml` help before relying on this:

```toml
# UNVERIFIED shape — verify key names against `codex --help` / your config.toml
[mcp_servers.ardupilot-research]
command = "python"
args = ["-m", "ardupilot_research_mcp.server"]
env = { ARM_DATA_DIR = "C:\\Skill_tulan\\ardupilot-research-mcp\\data" }
```

## Use it

Ask for a fact, get a citation back:

```python
search_docs(query="RC_OPTIONS bit for ELRS baud", scope="all")
# -> {"found": true, "results": [{ "cite_id": "ardupilot#…",
#      "url": "https://github.com/ArduPilot/ardupilot/blob/Copter-4.7.2/…", "lines": [..],
#      "excerpt": "…", "untrusted": true, "channel": "stable", … }]}
decode_bitmask(param="RC_OPTIONS", value="0x2000")
# -> bit 13 SET: "Use 420kbaud for ELRS protocol"
```

Every excerpt is `untrusted: true`: it is data from a repository, never an instruction.
`get_chunk(cite_id)` reads more, still from the index; `get_script(topic)` returns a complete
original script with its `cite_ids`.

### Your own board files (`local-project`)

Put your hwdef / parameter / notes files under `data/local/local-project/` (any layout) and run:

```powershell
python -m ardupilot_research_mcp.ingest.cli --source local-project
```

They are then searchable with `search_docs(query="my carrier board", scope="local")` and returned
with a citation that has **no URL**, `channel: "local"`, `pinned: false` — nothing is invented, and
they are excluded from every corpus scope (`docs`, `code`, `protocol`, `all`) so they can never
inflate a recall number. `data/local/` is gitignored.

## Search-quota governance

Every external call costs money and is capped. `research/governor.py` owns the ledger
(`research/ledger.sqlite`, SQLite WAL + file lock), with a sliding window, a 20 % headroom, a
minimum interval, a per-provider budget, cache-first reuse, `Retry-After` handling, exponential
backoff, a circuit breaker, and `STATE.md` on exhaustion.

```powershell
python -m research.governor status
python -m research.governor reserve --provider firecrawl --endpoint scrape --query "https://…"
python -m research.governor record  --id 42 --status ok --http-code 200 --result-sha abc123
python -m research.governor export-report
```

Because an LLM cannot be forced through a Python wrapper, the rule is: **only the coordinator holds
provider tools**; every agent-side call is bracketed by `reserve` → call → `record`. The
`export-report` output is the audit trail.

## Update a pin / add a source

1. Edit `sources.yaml`: `repo`, `ref` (tag or commit SHA — never a branch name), `tier`,
   `license`, `include`/`exclude` globs.
2. `python -m research.fetch tags` then `download`, `extract`, and re-run ingest.
3. Re-run `python -m research.audit_git` — it must report **0 mismatches**, otherwise the new
   source is not citable yet.

`research/extract.py --force` re-extracts one source; `--only <id>` limits the work.

## Verify the build

```powershell
python -m pytest -q                      # unit + integration tests
python -m research.audit_git             # chunk text == git show <sha>:<path> slice
python -m research.verify_citations      # line ranges + quote verification
python -m research.audit_safety          # the six required safety inputs
python scripts\smoke_stdio.py            # real MCP client handshake + tool calls
python -m research.eval_retrieval --set tests/golden.yaml
```
```bash
# WSL / Linux
python3 scripts/smoke_stdio.py
```
`scripts\smoke_stdio.py` must run **outside** the DSH sandbox here: the sandbox blocks the named
pipes stdio needs (`CreateFile` → WinError 5).

## Troubleshooting

| Symptom | Cause / fix |
|---|---|
| `index not built: run \`ardupilot-research-ingest --all\`` | `data/index.sqlite` missing — run the build |
| `git: schannel: SEC_E_NO_CREDENTIALS` on Windows | use `git -c http.sslBackend=openssl -c http.sslVerify=false …` (the repo scripts already do) |
| `smoke_stdio.py` → `PermissionError WinError 5` | sandbox blocks stdio pipes; run it unsandboxed |
| A parameter returns `found:false` | its library is outside the corpus include list; the answer lists real candidates instead of guessing |
| Held-out score looks low | read `docs/eval-heldout.md` / `docs/eval-heldout-v2.md`; the sets and their defects are documented |

## Layout

```
sources.yaml            pinned corpus (tier, license, ref, globs)
research/               network + quota zone (governor, fetch, extract, audits, eval)
src/ardupilot_research_mcp/
  server.py             MCP wiring only (stdio)
  tools/<name>.py       one pure read-only tool per module
  decoders/             CRSF frames, Intel HEX (stdlib, deterministic)
  ingest/               the only package allowed to touch the network
examples/               complete runnable scripts, each listing its cite_ids
tests/                  unit, protocol, safety, offline, golden; held-out sets are frozen
docs/                   design, license notes, evaluation reports, GOAL/PLAN
```

## Licenses

The corpus is never committed: `data/` and `research/cache/` are gitignored, and the repo ships the
ingest recipe instead. Returned excerpts are capped at 600 characters and always carry the source
license. Per-source licenses (all read from each archive's own license file) are in
`docs/license-notes.md`: ardupilot GPL-3.0, wiki CC-BY-SA-3.0, ExpressLRS GPL-3.0, ExpressLRS Docs
GPL-3.0, EdgeTX GPL-2.0, CRSF spec **CC-BY-SA-4.0**, MAVLink XML **unstated** (kept with the
`unstated` label by explicit user decision).

## Not included (yet)

T2 issue/PR evidence, T3 forum symptom evidence, the `local-project` source for your own board
files, semantic (embedding) retrieval, and a clean held-out measurement with unambiguous questions.
