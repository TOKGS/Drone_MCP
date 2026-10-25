# Held-out evaluation — single run, raw

- Set: `tests/heldout_locked.yaml`
- SHA-256: `0fa9493fe467d5d2ddf268d6c31da7405a3be86363bcb33be9bd555e196979d5`
  (matches `docs/heldout.sha256`; the file was not modified before or after this run)
- Build: commit `e3e68e1` + the 14-tool stage; index 63 808 chunks; server mcp 1.30.0
- Date: 2026-10-25
- Command: `python -m research.eval_retrieval --set tests/heldout_locked.yaml`

## Result (verbatim)

```
set=heldout_locked.yaml questions=30 k=5
recall@5 = 11/30 = 0.367
precision@1 = 8/30 = 0.267
MRR = 0.298
```

**This fails the acceptance target (recall@5 >= 0.8).** It is reported as a failure, not
explained away.

## What the 19 misses actually are

Reading the miss list reveals two different causes, and they must not be conflated:

**(a) Frozen expectation rejects a better answer.** The retriever returned a document that answers
the question, but the frozen set names a different file:

| id | question | frozen expectation | what the retriever returned |
|---|---|---|---|
| H04 | What does RC_OPTIONS control | `ardupilot:AP_RCProtocol` | `common/source/docs/common-rc-options.rst` (the dedicated page) |
| H14 | RC loss + failsafe | `ardupilot_wiki:common/source/docs` | `plane/source/docs/advanced-failsafe-configuration.rst` |
| H22 | serial passthrough | `ardupilot:AP_HAL` | `common-serial-passthrough.rst` |
| H28 | add a new parameter | `ardupilot:AP_Param` | `dev/source/docs/code-overview-adding-a-new-parameter.rst` |
| H26 | autotest entry point | `ardupilot:Tools/autotest` | `scripts/check_api_break.py` |

These are expectation defects in the frozen file (written before the corpus was fully understood),
not retrieval failures. They cannot be fixed now without destroying the freeze.

**(b) Genuine retrieval defects.** Examples: H09 (pre-arm causes) returned a CSS asset from
`expresslrs/src/html/...`; H15 (SITL) returned an autotest Python file instead of the dev docs;
H03 (ELRS packet rate) drifted to an unrelated doc. These are real quality problems: web assets are
indexed at all, and identifier-heavy English queries over-weight code.

## Consequence for the remaining rounds

- **This build's held-out score is 0.367.** Any retrieval change made from now on is informed by
  this run, so the set is no longer a clean hold-out: further numbers on it are *not* evidence of
  generalisation.
- The tunable set (`tests/golden.yaml`, 30 questions) scores recall@5 1.000 / precision@1 0.700 /
  MRR 0.811 on the same build, which is why the gap is best explained by the expectation defects
  above plus the two real defects.
- To make the acceptance criterion meaningful again, a **new** held-out set must be written and
  frozen (new SHA-256) that the implementer never sees; that is a decision for the user, not for me.
