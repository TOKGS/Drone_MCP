# The 4.6 variant corpus

The default corpus pins ArduPilot `Copter-4.7.2`. A fleet that still runs 4.6 firmware needs the
4.6 declarations instead, and a query answered from 4.7 is not merely stale, it is wrong:

| query | answer from the 4.7 pin | answer from the 4.6 pin |
|---|---|---|
| `lookup_param("ARMING_CHECK")` | `found:false` | `found:true`, `default_raw=ARMING_CHECK_ALL` |
| `lookup_param("ARMING_SKIPCHK")` | `found:true`, `default_raw=0` | `found:false` |
| `lookup_param("ATC_ACCEL_P_MAX")` | `found:false` (renamed to `ATC_ACC_P_MAX`) | `found:true`, `default_raw=..._DEFAULT_CDSS` |

So `sources-4.6.yaml` is a second pin set for the same seven sources with ArduPilot at
`Copter-4.6.2` (tag `1ebd4d996e8b6bbeb1462a9655c00aa861d5beef`). It is data, not code: the server
reads `sources.yaml` unless `ARM_SOURCES` points at another file, and it reads `data/` unless
`ARM_DATA_DIR` points at another tree.

## Build (measured 2026-10-26, this machine)

```powershell
$env:ARM_SOURCES  = "D:\Skill_tulan\ardupilot-research-mcp\sources-4.6.yaml"
$env:ARM_DATA_DIR = "D:\Skill_tulan\ardupilot-research-mcp\data\4.6"
$env:PYTHONPATH   = "D:\Skill_tulan\ardupilot-research-mcp\src"

python -m research.fetch download --tags research\tags-4.6.json
python -m research.extract --cache research\cache\repos-4.6
python -m ardupilot_research_mcp.ingest.cli --all --rebuild-index
python -m research.build_params
python -m research.build_mavlink
python -m ardupilot_research_mcp.ingest.cli --verify
```

`research.fetch download --tags` keeps its own `research/downloads-4.6.json` and
`research/cache/repos-4.6/`, so the two pins never share an archive. `--cache` points the extractor
at the same directory.

Measured run: download 76.9 s, extract 17.6 s, ingest 97.5 s, params 6.2 s, mavlink 6.5 s, verify
1.0 s, 207.9 s in total. Result: index 169.0 MB, corpus 104.5 MB, 6 768 documents, 79 558 chunks,
4 356 parameters, `verify: PASS` with all six structural checks at 0.

## Run it

`.mcp.json.example` carries both entries; the second one is:

```json
"ardupilot-research-4.6": {
  "type": "stdio",
  "command": "python",
  "args": ["-m", "ardupilot_research_mcp.server"],
  "env": {
    "PYTHONPATH": "D:\\path\\to\\ardupilot-research-mcp\\src",
    "ARM_REPO_ROOT": "D:\\path\\to\\ardupilot-research-mcp",
    "ARM_DATA_DIR": "D:\\path\\to\\ardupilot-research-mcp\\data\\4.6",
    "ARM_SOURCES": "D:\\path\\to\\ardupilot-research-mcp\\sources-4.6.yaml"
  }
}
```

`index_status` and `list_sources` report `Copter-4.6.2`, and every URL is
`.../blob/Copter-4.6.2/...`. A `cite_id` from one index does not resolve in the other; `get_chunk`
answers `unknown cite_id` rather than returning a chunk from the wrong release.

## What is verified for this variant

- `ingest --verify`: PASS, 0 chunks without a document or source, 0 bad line ranges, 0 FTS drift.
- Real MCP client over stdio: handshake, 14 tools, `smoke_failures=0`.
- `python -m research.eval_retrieval --set tests/heldout_v3.yaml --aggregate-only` on this index:
  recall@5 0.933, precision@1 0.833, MRR 0.873. The default 4.7 index scores 0.933, 0.833, 0.868 on
  the same frozen set, so retrieval quality carries over.

## What is not verified for this variant

- The frozen evidence packet (`docs/blackbox/run2`, `docs/blackbox/run3`) was recorded against
  4.7.2. `scripts/verify_a.py`, `verify_b.py`, `verify_cd.py`, `verify_e.py`, `verify_fg.py`,
  `blackbox_run.py` and `blackbox_independent.py` hardcode the 4.7.2 tag and SHA, so they do not
  describe this index. Re-recording them is a separate job, not a rebuild.
- Running the param tests against this data gives `6 failed, 37 passed`: the six assert 4.7 names
  and defaults on purpose (`ARMING_SKIPCHK`, `WP_SPD_UP`, golden precision on the 4.7 index). They
  are regression tests for the default pin, so the default data directory is the one `pytest` runs
  against; `145 passed, 1 skipped` there.
- The wiki source is the same `master` snapshot in both corpora, so it documents 4.7 features that
  do not exist in 4.6. The existing caveat is larger here, not smaller.

## Changing the pin

Edit `ref` and `version_label` in `sources-4.6.yaml`, update the `ardupilot` entry in
`research/tags-4.6.json` with the new tag and tarball URL, then rerun the build above with
`--rebuild-index`. `tests/test_variant.py` fails if the two files disagree, if the pin is not a
`Copter-4.6.x` tag, or if the variant drifts from `sources.yaml` anywhere other than the ArduPilot
pin and the `data/4.6` paths.
