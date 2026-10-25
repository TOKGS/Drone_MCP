# Research notes — what was verified, how, and what was wrong first

Every statement here was produced by a command run in this repository; nothing is recalled.

## MCP SDK (pinned `mcp==1.30.0`)

Read from the installed package instead of memory:

- `FastMCP(name=…, instructions=…)`, `.tool()`, `.add_tool(fn, annotations=…)`, `.run(transport="stdio")`
- client side: `mcp.ClientSession` + `mcp.StdioServerParameters(command=…, args=…, env=…, cwd=…)`
- `mcp.types.ToolAnnotations(readOnlyHint=True, idempotentHint=True, openWorldHint=False)`
- a tool's public signature must not contain `sqlite3.Connection` — pydantic cannot build a JSON
  schema for it, so `tools/_base.guarded` strips the first parameter via `__signature__`.

## Version resolution (constraint 1)

`git ls-remote` fails here with `schannel: SEC_E_NO_CREDENTIALS`; the working form is
`git -c http.sslBackend=openssl -c http.sslVerify=false …`. Two facts that cost real debugging:

- GitHub returns tags **alphabetically**, so `Copter-4.7.2` is not on page 1 — the resolver scans
  pages until it finds a `Copter-4.x.y` match (page 2 here).
- `--refs` omits peeled `^{}` lines; the sample tag here is lightweight, so the printed SHA is the
  commit SHA. The resolver still peels annotated tags explicitly (`rev-parse tags/<tag>^{commit}`).

## Licenses (constraint 5)

Read from the license file inside each pinned archive, not from memory. Two corrections to my
initial assumptions:

- `ardupilot_wiki` is **CC-BY-SA-3.0**, not GPL-3.0.
- `crsf_spec` (`tbs-fpv/tbs-crsf-spec`) is **CC-BY-SA-4.0**; `tbs-fpv/CRSF` does not exist (404).
- `mavlink` states (L)GPL-3.0 for the generator and MIT for generated code; the XML definitions
  themselves carry **no** license statement. The user explicitly chose to keep them with an
  `unstated` label.

## Corpus facts the decoders depend on

- CRC8 polynomial `0xD5` — `expresslrs/src/include/crsf_protocol.h:9`.
- "CRC includes Type and Payload … (doesn't include sync byte and frame length)" — `crsf.md:188`,
  and the 256-byte table's second entry (`0xD5`) is the regression vector in the tests.
- 0x16 = 16 channels × 11 bits in 22 bytes, `ticks_to_us = (ticks-992)*5/8+1500` — `crsf.md:521-527`.
- ArduPilot parameter metadata is `// @Param:` blocks plus a declaration; **not all** declarations
  are `AP_GROUPINFO` (ArduCopter uses `GSCALAR` wrappers), so the parser keys on the quoted name.
- `RC_OPTIONS` is declared as `@Param: _OPTIONS` in `RC_Channels_VarInfo.h` (group-suffixed name);
  its `@Bitmask` bit 13 is "Use 420kbaud for ELRS protocol".
- Board hwdefs inherit through `include ../<Board>/hwdef.inc`, so `SERIAL_ORDER` is often not in the
  board's own file.

## Quota (constraint 4)

- Firecrawl balance was **observed** (`1106 credits`); its request rate limits are **not** exposed to
  the MCP client, so the conservative defaults in `limits.yaml` are labelled `ASSUMED`.
- Exa and built-in `web_search` expose no quota metadata at all → also `ASSUMED`.
- Ledger totals for the whole build: firecrawl 0, exa 0, web_search **1** (one fetch reservation,
  recorded as `error` after a cross-origin redirect), github ~40 metered calls, codeload raw
  downloads at cost 0.

## Client registration (constraint: do not guess)

- OpenCode: verified from `packages/web/src/content/docs/mcp-servers.mdx` (`type: "local"`,
  `command` array, `environment`, `enabled`).
- Claude Code: verified from `plugins/plugin-dev/skills/mcp-integration/examples/stdio-server.json`
  (`mcpServers` map with `command`/`args`/`env`); the project-scope file name is unverified.
- Codex: `[mcp_servers.<name>]` sections verified from its repo; the **stdio key names are
  unverified** because the config reference redirects to a login page. Nothing was invented.

## Things that were wrong first (and how they were caught)

1. `cite.py` imported `urllib.parse` → caught by the offline import test; replaced with a local
   percent-encoder.
2. Chunking produced a 313 KB chunk from a generated `web-*.h` array → hard size cap added.
3. `board_info` matched a board's README because paths were ordered by length → definition file
   ranked first; then `SERIAL_ORDER` was still missing → include-following added.
4. The FIRST held-out set scored 0.367 partly because its frozen expectations rejected better
   answers (`common-rc-options.rst`, `advanced-failsafe-configuration.rst`). That set was measured
   once and never edited; a blind mechanical set (v2) scored 0.533. Both failures are published.
