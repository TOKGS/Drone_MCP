# HANDOFF

Read this first in every new round. Everything below is raw output I ran, or explicitly
marked UNVERIFIED / NOT RUN.

## Current state

- **Corpus: complete for v1.** 7 sources pinned, cloned at their pinned refs, extracted,
  ingested, and audited against Git blobs (see gate 1).
- **Index:** `data/index.sqlite` — 63 652 chunks, 4 927 documents, 7 sources.
- **cite_id is content-addressed** now: `ardupilot#fa0de4fb47c0c141` (16 hex of
  `sha256(source|path|lines|sha256(text))`), stable across re-ingest, independent of row ids.
- **Server: does not exist yet.** 0 of 14 tools implemented, so no MCP handshake has run.
- **Quota:** firecrawl 0 · exa 0 · web_search 0 · github 30 calls · codeload 7 calls.
  Still zero search quota spent.

## Gates run this round (raw)

```
1) chunk/line fidelity vs real Git objects
source              chunks  mismatch  note
ardupilot            28453         0  ok
ardupilot_wiki       26580         0  ok
crsf_spec              157         0  ok
edgetx                 770         0  ok
expresslrs            3716         0  ok
expresslrs_docs       3341         0  ok
mavlink                635         0  ok
total chunks = 63652, total mismatch = 0
```

```
2) clones at pinned refs (git rev-parse HEAD)
ardupilot        cloned  head=fb773567896014da  pin_match=True     (Copter-4.7.2)
ardupilot_wiki   cloned  head=828de1f225dace34  pin_match=True
mavlink          cloned  head=eec8824212c1fe8c  pin_match=True
expresslrs       exists  head=a9d4a9cb5b5687c4
expresslrs_docs  cloned  head=5ed656b6ebc7a38b  pin_match=True
crsf_spec        cloned  head=a73f7dc5386e5b87  pin_match=True
edgetx           cloned  head=0ebe2e98b2085e22  pin_match=True     (v2.12.5)
```

```
3) tests
27 passed in 21.37s        ($ python -m pytest -q)   exit=0
```

```
4) invoice of one real citation (not a mock)
{"cite_id": "ardupilot#fa0de4fb47c0c141", "source_id": "ardupilot",
 "repo": "ArduPilot/ardupilot", "ref": "Copter-4.7.2", "channel": "stable",
 "unreleased": false, "version": "Copter-4.7.2",
 "url": "https://github.com/ArduPilot/ardupilot/blob/Copter-4.7.2/libraries/AP_RCProtocol/AP_RCProtocol_CRSF.cpp#L1-L19",
 "lines": [1, 19], "tier": "T1", "license": "GPL-3.0", "untrusted": true}
excerpt_len=600 verify_quote=True
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
