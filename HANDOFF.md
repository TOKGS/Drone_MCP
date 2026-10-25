# HANDOFF

Read this first in every new round. Everything below is raw output I ran, or explicitly
marked UNVERIFIED / NOT RUN.

## Current state

- **Server exists and speaks MCP over stdio** (4 of 14 tools). Handshake verified with a real
  client: `server=ardupilot-research version=1.30.0 protocol=2025-11-25`.
- **Corpus:** 7 sources pinned → 4 927 documents → 63 652 chunks → `data/index.sqlite` (111.8 MB).
- **Distillation:** `chunks.distilled` feeds FTS only (wiki markup ratio 0.696); `chunks.text`
  stays verbatim for citations.
- **Serving is fully local:** the index alone answers; corpus files are not read at serve time.
- **Quota:** firecrawl 0 · exa 0 · web_search 0 · github 30 · codeload 7. Zero search quota spent.

## Gates run this round (raw)

```
handshake: server=ardupilot-research version=1.30.0 protocol=2025-11-25
tools(4): ['search_docs', 'get_chunk', 'list_sources', 'index_status']
[search_docs] found=true  cite_id=ardupilot#fdfff6f8575eb291  path=libraries/AP_Math/crc.cpp L77-L103
[get_chunk]   cite_id ok, context expanded to L51-L135
smoke_failures=0
```

```
31 passed in 21.16s        ($ python -m pytest -q)
```

```
distil effect: wiki chunks=26580  mean(distilled/text)=0.696
Vietnamese: "mất tín hiệu tay cầm" -> expansions ['mất tín hiệu -> rc loss/failsafe/link quality',
            'tay cầm -> transmitter/radio/rc']  top hit: copter/source/docs/radio-failsafe.rst
out-of-corpus: "how do I bake sourdough bread" -> found:False, results 0
```

```
fidelity (unchanged after distillation): 63652 chunks, total mismatch = 0
```

Bugs found and fixed this round: tool parameter `query` shadowed the `query` module;
`sqlite3.Connection` in a tool signature broke SDK schema generation (public signature now drops
it); out-of-corpus questions matched stopwords and wrongly returned `found:true` (stopword filter).


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

- **License-header boilerplate is still indexed** — the first chunk of many `.cpp` files is the
  GPL header (see the citation above), which will pollute BM25 ranking. Must be stripped at
  chunk time while keeping line offsets, then re-ingested (planned action 1).
- **No server, no tools** → 0/14; `troubleshoot` safety outputs **NOT RUN**;
  MCP Inspector command **NOT RUN**; client registration **UNVERIFIED**.
- **No retrieval code** → recall@5 / precision@1 / MRR **NOT RUN**; `golden.yaml` does not exist.
- **Mutation testing ≥90 %** **NOT RUN**.
- **T2 (issues/PR) and T3 (forum) are not ingested** — no evidence tier below T1 yet.
- `local-project` source (user's own board files) not created.
- `expresslrs_docs` pins a commit on `master`, so it is `snapshot`/`unreleased` by design.
- Windows-only quirks: `git` needs `-c http.sslBackend=openssl -c http.sslVerify=false`;
  `Get-PSDrive.Free` returns null under the sandbox (use `[System.IO.DriveInfo]`).

## Next 5 actions

1. Strip per-file license/copyright headers before chunking (keep `line_start` at real content),
   re-ingest, re-run `research.audit_git` (gate must stay 0 mismatch).
2. Add `server.py` + `guard.py` + `search_docs`/`get_chunk`, verify the stdio handshake with the
   pinned `mcp==1.30.0` client, and record the MCP Inspector command.
3. Build retrieval (FTS5 BM25 + identifier boost + `glossary.vi-en.yaml`) and write
   `tests/golden.yaml` (30 questions); tune **only** on golden.
4. Implement the remaining tools, starting with decoders (CRC8 0xD5, Intel HEX, 11-bit unpack,
   bitmask) then `troubleshoot` with the mandatory safety block; add negative tests
   (`found:false`, out-of-corpus, refuse arm/flash).
5. README + client registration docs (OpenCode / Claude Code / Codex) from their own pinned docs,
   then a single held-out evaluation run with recall@5 / precision@1 / MRR, plus mutation run.
