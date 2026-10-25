# Improvement pass, 2026-10-25

Follow-up to `docs/FIX_REPORT.md`. The eight defects are closed; this pass takes the items that were
listed as "do next" and lands them with evidence. Every number below is output of a command in this
repository.

## Retrieval

**C1 is fixed.** A document can hold two near-identical paragraphs: `crsf.md` states the frame CRC
polynomial (`0xD5`, line 190) and, further down, the Command-frame polynomial (`0xBA`, line 976).
BM25 scored the Command paragraph higher because it repeats the same words, so the citation quoted
the wrong constant.

The picker inside a winning document now sorts by three keys: whole-word hits (a match inside
`Command_CRC8` no longer counts for `crc8`), then heading width (a chunk under "Direct Commands" is
narrower than the query), then bm25 (`src/ardupilot_research_mcp/query.py`, `_boundary_hits`,
`_heading_extra`).

```
query "CRC8 polynomial CRSF"
  before: crsf_spec/crsf.md rank 3, excerpt contains 0xBA
  after : crsf_spec/crsf.md rank 3, excerpt contains 0xD5 and not 0xBA
golden    recall@5 1.000  P@1 0.767  MRR 0.859   (unchanged)
heldout_v3 recall@5 0.933  P@1 0.833  MRR 0.868   (unchanged)
```

Three frozen blackbox cases still miss (`C4`, `C10`, `C11`). Fixing those needs a wider retrieval set
first, otherwise the change is tuned to three questions.

## Test infrastructure

**Mutation harness re-pointed.** Three mutants targeted code the fix round rewrote and reported
"mutation target not found"; M06 now targets `c_div`, M11 the verb-plus-object rule, M12 the refusal
excerpt filter. M14 (stopword filter removed) is now killed by
`tests/test_query.py::test_stopwords_never_reach_the_index_query`.

M12 cannot be killed, and that is a property of the code rather than a missing test: the hardcoded
`"value 0" and "disable"` clause duplicates a `dangerous_excerpt` pattern, so no realistic input
separates the mutant from the original. The harness now carries an `equivalent` flag and reports it
outside the score instead of pretending it was caught.

```
mutants=14 killed=14 survived=0 errors=0 equivalent=1 score=1.000
```

**New hardening tests** (`tests/test_hardening.py`): the guard refuses past its limit and recovers
after `Guard.reset()`, `safe_data_path` rejects traversal, and a directory symlink that points outside
`data/` is rejected. The symlink case skips on this Windows account because it cannot create
directory symlinks, so junction traversal stays unproven here.

`tests/conftest.py` now resets the guard through `Guard.reset()` instead of poking `_calls`.

## Reproducibility

**`research.build_all`** runs fetch, extract, ingest, params, mavlink and the verify stage as separate
processes, then optionally the gates, and stops at the first failure so the error names the stage.
`--dry-run` prints the commands, `--prune-cache` deletes the 2.7 GB of archives once the index exists.

**`research.extract` no longer fails on the local overlay.** It skipped nothing before, so a plain
`python -m research.extract` exited 1 on `local-project`, which has no tarball by design. It now
prints `local-project skipped (local source, no tarball; ingest reads data/local)` and exits 0.

**`scripts/blackbox_run.py --out DIR`** writes a run to a directory of your choice. Before, a second
run needed a worktree because the script refuses to overwrite `docs/blackbox/raw`.

## Guards that keep the repository honest

- `scripts/check_readmes.py` fails when either README contains an em dash, an en dash, one of the
  stock AI phrases, a broken internal anchor, or numbers that disagree with the other README. This
  exists because the project now ships two READMEs and nothing else compared them.
- `scripts/bench.py` measures `search_docs` p50/p95 over the golden questions with a budget. Measured
  on this machine: p50 58.5 ms, p95 186 ms to 339 ms depending on warm cache, budget 400 ms.
- `.github/workflows/ci.yml` runs pytest, the README gate and traceability on Windows and Ubuntu for
  every push, and a weekly job builds the index and runs the documented gates.

## Housekeeping

- `LICENSE` added (MIT). The corpus keeps its own licenses and is not redistributed.
- `.mcp.json` is per-machine again: it holds absolute paths, so it is now gitignored and only
  `.mcp.json.example` is committed.
- READMEs rewritten without em dashes or stock AI phrasing (English and Vietnamese), and both are
  checked by the gate above.

## Not done in this pass

- Code coverage. `pip install coverage` did not finish in this session, so there is no number to
  report; `pyproject.toml` does not list it yet.
- Ranking for `C4`, `C10`, `C11`. Deliberately deferred until the retrieval set is larger.
- Worktree cleanup: `wt-A` through `wt-F`, `bb-run2`, `drone-mcp-verify` and `client-verify` still
  exist on this machine, together about 1 GB of index copies.
- A logged-in Claude Code session. The connection and tool list are proven there, and the
  model-issued tool call is proven on OpenCode (see the client section above).
