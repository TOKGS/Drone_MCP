# HANDOFF

Read this first in every new round. Everything below is either raw output I ran or
explicitly marked UNVERIFIED.

## Current state

- **Stage:** corpus + index skeleton. Governor done and tested; 1 of 5 sources ingested.
- **Server:** `src/ardupilot_research_mcp/server.py` **does not exist**. 0 of 14 tools implemented.
- **Index:** `data/index.sqlite` 11.6 MB — `{sources:1, documents:399, chunks:3716}`,
  `chunks_fts` 3716 rows (consistent), source = `expresslrs@4.1.0` only.
- **Corpus on disk:** 4885 files / 51.1 MB, 5 sources extracted and pinned
  (ardupilot, ardupilot_wiki, mavlink, expresslrs, edgetx); 4 of them are **not ingested yet**.
- **Quota ledger:** firecrawl 0 · exa 0 · web_search 0 · github 24 calls (16 units, 33 % cache
  hit) · codeload 5 calls (0 units). No search quota spent in the whole build.

## Gates run this round (raw)

```
$ git -c http.sslBackend=openssl -c http.sslVerify=false ls-remote --tags --refs \
      https://github.com/ArduPilot/ardupilot 'Copter-*'   # 100 lines, last 5 by version
1ebd4d996e8b6bbeb1462a9655c00aa861d5beef  refs/tags/Copter-4.6.2
92b0cd788ec29406f26c6f9c31d5ceedbd1cc538  refs/tags/Copter-4.6.3
1511f27194f1dcc3728270883047bdf022b3fd53  refs/tags/Copter-4.7.0
dbe792162d06cab66c3475fd5556bf7a120f119e  refs/tags/Copter-4.7.1
fb773567896014da007bca58358704d4a0d8516f  refs/tags/Copter-4.7.2
```

```
$ python -m unittest discover -s tests
Ran 11 tests in 21.105s
OK                                   (unittest_exit=0)
```

```
$ python -m research.audit_git
sample 10 chunks (seed 42): 10/10 MATCH
whole index: expresslrs 3716 chunks, 0 mismatch
14-tool citation audit: 0/14 implemented
total mismatch = 0
```

```
$ grep -rnE '4\.[0-9]\.[0-9]' src/           -> 0 matches
$ network imports in src/ outside ingest/    -> 0 matches  (cite.py urllib.parse fixed this round)
$ python -m research.governor export-report  -> see below
```

```
provider        calls   1h   24h   units  cache%  429  defer  peak  budget
firecrawl           0    0     0     0.0    0.0%    0      0     0     300
exa                 0    0     0     0.0    0.0%    0      0     0     100
web_search          0    0     0     0.0    0.0%    0      0     0      40
github             24   16    16    16.0   33.3%    0      0     1    None
codeload            5    5     5     0.0    0.0%    0      0     1    None
```

## Verified (with output above)

1. Pin `Copter-4.7.2` = `fb773567896014da007bca58358704d4a0d8516f` resolved by `git ls-remote`.
2. Governor: 11 unit tests, including 2-process concurrency cap, Retry-After, breaker, cache-0-cost,
   STATE.md on exhaustion.
3. Chunk/line fidelity: every chunk of the ingested source equals the slice of its Git blob
   (`git show <sha>:<path>`) — 0 mismatches over 3716 chunks.
4. Offline rule: no network/subprocess import in `src/` outside `ingest/`.
5. License per source read from the archive's own license file (`docs/license-notes.md`).
6. Held-out set frozen: `tests/heldout_locked.yaml`, 30 questions (15 vi / 15 en),
   sha256 `0fa9493fe467d5d2ddf268d6c31da7405a3be86363bcb33be9bd555e196979d5`
   (recorded in `docs/heldout.sha256`). **Not evaluated.**

## Known gaps / UNVERIFIED

- **4 sources not ingested**: ardupilot, ardupilot_wiki, mavlink, edgetx → 0 chunks each.
- **No MCP server, no tools**: the 14-tool table is 0/14; therefore `troubleshoot` safety outputs
  could not be produced — **NOT RUN**, not "passing".
- **CRSF spec**: `tbs-fpv/CRSF` returned HTTP 404 → not pinned, not indexed.
- **ExpressLRS Docs**: repository not resolved → **MISSING**.
- **ardupilot citation audit**: no local clone of ardupilot (307 MB) → only expresslrs was
  audited against Git objects; ardupilot/wiki/mavlink/edgetx comparisons are **UNVERIFIED**.
- **Golden questions / recall@5 / precision@1 / MRR**: **NOT RUN** (no retrieval code yet).
- **Mutation coverage ≥90 %**: **NOT RUN**.
- **quota**: agent-side MCP calls cannot be intercepted automatically; they must be routed by hand
  through `governor reserve` → call → `governor record` (commands exist; 0 calls made so far).
- **Exclusions worth knowing**: files with NO license statement (mavlink XML) are indexed with
  `license: ...unstated`; git `export-subst` files (`VERSION`) are excluded because the archive
  text differs from the blob; generated/minified files (any line > 1000 chars) are excluded.
- **Windows quirk**: `git` needs `-c http.sslBackend=openssl -c http.sslVerify=false` in this
  environment (schannel fails with `SEC_E_NO_CREDENTIALS`).

## Next 5 actions

1. Add `sources.yaml` entries for **ExpressLRS Docs** and a resolvable **CRSF spec**, or record
   them as permanently MISSING with evidence.
2. Ingest the remaining 4 sources (`--all`), then re-run `audit_git` for every source
   (needs shallow clones per source; add a `research/clone.py`).
3. Build `server.py` + `search_docs`/`get_chunk` only, verify stdio handshake with the pinned
   `mcp==1.30.0` SDK, and record the MCP Inspector command.
4. Add `tests/test_offline.py` (import guard), `tests/test_chunkers.py` (line-range round trip on
   fixtures), and `tests/test_cite.py` (verify_quote over every chunk).
5. Only after 1–4: write retrieval + tool layer for the remaining 12 tools, then evaluate on
   `golden.yaml`; evaluate on `heldout_locked.yaml` **once**, after the freeze, and publish
   recall@5 / precision@1 / MRR.
