# License notes

Every license below was read from the license file copied out of the pinned archive
(`docs/licenses/<source>-<file>`), not from memory. Retrieved 2026-10-25.

| source | pin | tier | license (verified) | evidence |
|---|---|---|---|---|
| `ardupilot` | `Copter-4.7.2` | T1 | **GPL-3.0** | `COPYING.txt`: "GNU GENERAL PUBLIC LICENSE / Version 3, 29 June 2007" |
| `ardupilot_wiki` | commit `828de1f2` (2026-10-24) | T1 | **CC-BY-SA-3.0** | `LICENSE`: "CC3.0 BY SA (Attribution-ShareAlike 3.0 Unported)" |
| `mavlink` | commit `eec88242` (2026-10-22) | T1 | **(L)GPL-3.0 generator + MIT exception for generated code; XML definition license unstated** | `COPYING`: generator is "(L)GPL v3", generated output offered under MIT; no license text covers `message_definitions/*.xml`, and those files carry no header (checked `common.xml`) |
| `expresslrs` | `4.1.0` | T1 | **GPL-3.0** | `LICENSE`: "GNU GENERAL PUBLIC LICENSE / Version 3, 29 June 2007" |
| `edgetx` | `v2.12.5` | T1 | **GPL-2.0** | `LICENSE`: "GNU GENERAL PUBLIC LICENSE / Version 2, June 1991" |

## What the product does with each license

- **Read-only, no redistribution of the corpus.** `data/` and `research/cache/` are
  gitignored; the repository ships only the ingest recipe (`sources.yaml` + pinned refs),
  never the upstream text. This keeps GPL/CC-BY-SA redistribution duties out of the repo.
- **Short excerpts only.** Every returned documentary item is capped at **600 characters**,
  verbatim from the indexed chunk, and always paired with a SHA-pinned permalink,
  the license tag and `untrusted: true`. Longer material is returned as `path + lines`
  so the caller opens it upstream.
- **Attribution.** `cite.py` puts `source_id`, `repo`, `ref`, `license` and the permalink
  in every citation, which satisfies CC-BY-SA attribution and GPL source-offer by pointer.
- **Original code.** `examples/` and `src/` are written from scratch; no upstream source is
  copied into the repository. Behaviour is cited, not code.
- **MAVLink XML.** The definitions' license is not stated upstream. They are indexed for
  retrieval and cited by permalink; if the user requires a stricter posture, the
  `mavlink_message` tool can be restricted to value lookups without verbatim excerpts.

## Not bundled in v1

`MethodicConfigurator`, `fossuav/aap` and similar GPL projects are *reference-only*
(`§4`): linkable from answers, never indexed as text and never quoted at length.

## Decisions taken with the user

- **2026-10-25 — MAVLink XML license unstated upstream.** User chose: keep the definitions in
  the index and return ≤600-character verbatim excerpts, with the citation carrying
  `"license": "(L)GPL-3.0 generator; MIT generated code; XML definitions unstated"`.
  This is the only source in v1 whose license is not explicitly stated upstream; if that
  ever needs tightening, the `mavlink_message` tool can drop excerpts without a re-ingest.

