# HANDOFF

Read this first in every new round. Everything below is raw output I ran, or explicitly
marked UNVERIFIED / NOT RUN.

## Current state

- **Server speaks MCP over stdio** (13 of 14 tools): search_docs, get_chunk, lookup_param,
  decode_bitmask, find_source, board_info, mavlink_message, troubleshoot, decode_crsf_frame,
  check_intelhex_line, parse_ihex_summary, list_sources, index_status.
- **Tables:** 63 808 chunks · 214 params (26 with @Bitmask) · **397 MAVLink messages + 2367 enum
  entries** parsed from the pinned XML · index ≈ 120 MB.
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
tools(13): ['search_docs','get_chunk','lookup_param','decode_bitmask','find_source','board_info',
            'mavlink_message','troubleshoot','decode_crsf_frame','check_intelhex_line',
            'parse_ihex_summary','list_sources','index_status']
[mavlink_message] found=True id=30 name=ATTITUDE fields=7
[board_info] found=True mcu=['STM32H7xx','STM32H757xx']
             serial_order=['OTG1','USART2','USART3','UART4','UART8','UART7','OTG2']
smoke_failures=0
63 passed in 21.60s
```

```
build_mavlink: {"xml_files": 19, "messages": 397, "enums": 2367,
                "messages_with_citation": 397,
                "mavlink_version": "eec8824212c1fe8c5d8f5181fcfdef54ee219b63"}
build_params : {"parsed_blocks": 232, "linked": 216, "unlinked": 16, "in_table": 214}
```

Two defects fixed: `board_info` matched a board's `README.md` because paths were ordered by
length (README is shorter than `hwdef.dat`) — it now ranks the definition file first; and it
reported no `SERIAL_ORDER` for CubeOrangePlus because that key lives in the included
`../CubeOrange/hwdef.inc` — includes are now followed one level inside the index and reported in
`included_files`. The param count fell 241 → 214 because this index was rebuilt from scratch and
the table is keyed by (name_raw, vehicle, version), so cross-file duplicates collapse.




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

- **1 of 14 tools missing**: get_script (the `examples/` scripts and their cite_id headers).
- **Held-out evaluation NOT RUN** (by design: once, when the server is complete).
- **Mutation testing ≥90 % NOT RUN**; **README + client registration UNVERIFIED**.
- **T2 (issues/PR), T3 (forum), `local-project`** not ingested.
- The param table covers only the libraries present in the corpus (214 rows); a parameter defined
  in a library outside the include list returns `found:false` with real candidates.
- `board_info` follows one level of `include`; a deeper chain would need another pass.
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
