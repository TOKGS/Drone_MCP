# HANDOFF

Read this first in every new round. Everything below is raw output I ran, or explicitly
marked UNVERIFIED / NOT RUN.

## Current state

- **Server speaks MCP over stdio** (11 of 14 tools): search_docs, get_chunk, lookup_param,
  decode_bitmask, find_source, troubleshoot, decode_crsf_frame, check_intelhex_line,
  parse_ihex_summary, list_sources, index_status.
- **Decoders are corpus-derived, not recalled**: CRC8 poly 0xD5 (`crsf_protocol.h` L9), CRC
  coverage "Type and Payload, not sync/length" (`crsf.md` L188), 0x16 = 16 × 11-bit channels in
  22 bytes with `(ticks-992)*5/8+1500` (`crsf.md` L521-527). Intel HEX checksum is the two's
  complement of the summed bytes; record types 00/01/02/03/04/05.
- **Safety gate is live and tested**: the six required inputs classify correctly and
  `troubleshoot` refuses safety bypasses, carrying `Props off for bench tests. SITL before
  hardware.` plus a `CONFIRM:` line; "what does ARMING_CHECK do" is still answered with
  evidence (confidence high) instead of being refused.
- **Parameter table built from source metadata**: 241 rows (24 with `@Bitmask`), every row linked
  to the chunk that declares it. RC_OPTIONS resolves to `_OPTIONS` in `RC_Channels_VarInfo.h`
  and decodes bit 13 = "Use 420kbaud for ELRS protocol".
- **Corpus:** 7 sources pinned → 4 939 documents → **63 808 chunks** → `data/index.sqlite`.
  ardupilot now also carries `libraries/RC_Channel` and `libraries/AP_Arming` (parameter and
  arming-check definitions were missing and made an RC_OPTIONS question unanswerable).
- **Distillation:** `chunks.distilled` feeds FTS only (wiki markup ratio 0.696); `chunks.text`
  stays verbatim for citations.
- **Serving is fully local:** the index alone answers; corpus files are not read at serve time.
- **Quota:** firecrawl 0 · exa 0 · web_search 0 · github 30 · codeload 7. Zero search quota spent.

## Gates run this round (raw)

```
handshake: server=ardupilot-research version=1.30.0 protocol=2025-11-25
tools(11): ['search_docs','get_chunk','lookup_param','decode_bitmask','find_source',
            'troubleshoot','decode_crsf_frame','check_intelhex_line','parse_ihex_summary',
            'list_sources','index_status']
[decode_crsf_frame] found=True crc_ok=True type=Link statistics
[find_source]       found=True path=libraries/AP_RCProtocol/AP_RCProtocol_CRSF.cpp lines=[1, 19]
smoke_failures=0
58 passed in 21.99s
```

Decoder vectors come from the corpus itself: `crc8(b"\x01") == 0xD5` matches the spec's CRC
table (`0x00, 0xD5, 0x7F, 0xAA …`), a frame built with that CRC parses as CRC-valid and one
corrupted byte is reported invalid, 11-bit channel pack/unpack round-trips, and the canonical
Intel HEX data record `:10010000…0140` validates while a one-nibble edit does not.

Three defects fixed: `paths.py` used a relative import beyond the package; decoder tools were
wrongly gated on an existing index (they are pure computation, now `guarded_pure`); and the
governor's `FileLock` raised `PermissionError` when a concurrent Windows process unlinked the lock
file mid-open — it now retries exactly like "busy" (this was a real multi-process flake).




## Verified

1. 100 % of excerpts match the Git blob at the cited lines (63 652 chunks, 0 mismatches).
2. All pins resolved by `git ls-remote` / commits API; channel rule: tag → `stable`,
   commit → `snapshot` + `unreleased: true`.
3. License per source read from the archive's own license file (`docs/license-notes.md`);
   `crsf_spec` is CC-BY-SA-4.0, `mavlink` XML is unstated (user approved indexing).
4. Offline rule enforced by `tests/test_offline.py` (no network imports outside `ingest/`,
   no `shell=True`, no `eval/exec`, no hardcoded `X.Y.Z` in `src/`).
5. Held-out set frozen: 30 bilingual questions, sha256 `0fa9493f…` in `docs/heldout.sha256`.
   **Still not evaluated.**

## Known gaps / UNVERIFIED

- **3 of 14 tools missing**: board_info, mavlink_message, get_script.
- **MAVLink tables empty** (`mavlink_msgs`, `mavlink_enums` = 0): XML not parsed yet.
- **Held-out evaluation NOT RUN** (by design: once, when the server is complete).
- **Mutation testing ≥90 % NOT RUN**; **README + client registration UNVERIFIED**.
- **T2 (issues/PR), T3 (forum), `local-project`** not ingested.
- The param table covers only the libraries present in the corpus (241 rows); a parameter defined
  in a library outside the include list returns `found:false` with real candidates.
- A refusal's citations may include a wiki excerpt that itself mentions `blob/master` in its text;
  our own citation URLs are always pinned (checked by `tests/test_cite.py`).
- Mechanical note: a `git`-based audit needs the shallow clones under `research/cache/git/`
  (gitignored); without them the audit reports `no-clone`.

## Next 5 actions

1. Build the parameter table from ArduPilot metadata (`AP_Param` var_info + generated
   `apm.pdef`), then `lookup_param` / `decode_bitmask` with citations.
2. Parse `mavlink/message_definitions` XML into `mavlink_msgs` / `mavlink_enums`, then
   `mavlink_message`.
3. Add `find_source`, `board_info` (hwdef parsing), and the three decoders
   (CRC8 0xD5, Intel HEX, 11-bit unpack) with unit tests and test vectors.
4. `troubleshoot` with the mandatory safety block + the 6 required prompt cases, plus negative
   tests (refuse arm/flash, dark corners) and `get_script`.
5. README + client registration, then the single held-out run (recall@5 / precision@1 / MRR)
   and a mutation run.
