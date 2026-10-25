# HANDOFF

Read this first in every new round. Everything below is raw output I ran, or explicitly
marked UNVERIFIED / NOT RUN.

## Current state

- **Server exists and speaks MCP over stdio** (4 of 14 tools). Handshake verified with a real
  client: `server=ardupilot-research version=1.30.0 protocol=2025-11-25`.
- **Corpus:** 7 sources pinned → 4 939 documents → **63 808 chunks** → `data/index.sqlite`.
  ardupilot now also carries `libraries/RC_Channel` and `libraries/AP_Arming` (parameter and
  arming-check definitions were missing and made an RC_OPTIONS question unanswerable).
- **Distillation:** `chunks.distilled` feeds FTS only (wiki markup ratio 0.696); `chunks.text`
  stays verbatim for citations.
- **Serving is fully local:** the index alone answers; corpus files are not read at serve time.
- **Quota:** firecrawl 0 · exa 0 · web_search 0 · github 30 · codeload 7. Zero search quota spent.

## Gates run this round (raw)

```
set=golden.yaml questions=30 k=5
recall@5 = 30/30 = 1.000
precision@1 = 21/30 = 0.700
MRR = 0.811
```

Tuning path (each step measured, no guessing): baseline 0.633 / 0.300 / 0.436
→ path words added to the search-only column, identifier LIKE pass, heading boost,
file-named-after-parameter boost, glossary terms, and `libraries/RC_Channel` +
`libraries/AP_Arming` added to the ardupilot include list → 1.000 / 0.700 / 0.811.

Two "misses" were wrong expectations, not retrieval failures, and the evidence is in the
corpus: `crsf.md` is the CRC8 spec page, and `common/source/docs/common-rc-options.rst` is the
dedicated RC_OPTIONS page (it exists and contains the parameter twice). The golden file now
accepts every verified target instead of a single guessed path.

```
RC_OPTIONS query: rank 1 = ardupilot_wiki/common/source/docs/common-rc-options.rst (score -24.58)
out-of-corpus "how do I bake sourdough bread" -> found:false
31 passed in 21.34s
```



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

- **10 of 14 tools missing**: lookup_param, decode_bitmask, find_source, board_info,
  mavlink_message, troubleshoot, get_script, decode_crsf_frame, check_intelhex_line,
  parse_ihex_summary. `troubleshoot` safety outputs are therefore **NOT RUN**.
- **Params and MAVLink tables are empty** (`params`, `mavlink_msgs`, `mavlink_enums` = 0 rows):
  parameter metadata generation and MAVLink XML parsing are not built yet.
- **Held-out evaluation NOT RUN** (by design: it is evaluated once, when the server is complete).
- **Mutation testing ≥90 % NOT RUN**; **README + client registration UNVERIFIED**.
- **T2 (issues/PR), T3 (forum), `local-project`** not ingested.
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
