# Mutation report

- selected mutants: **18** (hand-written semantic changes, scored)
- killed: **18**
- survived: **0**
- errors: 0
- equivalent and excluded from the score: 1
- score: **1.000** (target 0.90)

**Target met** (>= 0.90).

| mutant | file | change | result | detail |
|---|---|---|---|---|
| M01 | `cite.py` | cite_id length changes | killed | 1 failed, 2 passed in 0.24s |
| M02 | `cite.py` | channel rule inverted | killed | 1 failed, 2 passed in 0.31s |
| M03 | `cite.py` | quote verification inverted | killed | 1 failed, 3 passed in 0.33s |
| M04 | `decoders/crsf.py` | wrong CRC polynomial | killed | 1 failed in 1.13s |
| M05 | `decoders/crsf.py` | CRC bit test inverted | killed | 1 failed in 1.15s |
| M06 | `decoders/crsf.py` | microsecond conversion off by one | killed | 1 failed, 2 passed in 1.20s |
| M07 | `decoders/crsf.py` | channel bit width wrong | killed | 1 failed, 2 passed in 1.15s |
| M08 | `decoders/crsf.py` | sync detection inverted | killed | 1 failed, 1 passed in 1.18s |
| M09 | `decoders/ihex.py` | checksum sign dropped | killed | 1 failed, 8 passed in 1.20s |
| M10 | `decoders/ihex.py` | length check inverted | killed | 1 failed, 8 passed in 1.12s |
| M11 | `safety.py` | verb plus object rule demoted | killed | 1 failed, 2 passed in 0.35s |
| M12 | `safety.py` | refusal excerpt filter disabled (equivalent: dangerous_excerpt regex catches the same sentences) | SURVIVED | 31 passed in 2.03s |
| M13 | `paths.py` | path containment inverted | killed | 1 failed, 10 passed in 1.26s |
| M14 | `query.py` | stopword filter removed | killed | 1 failed, 31 passed in 12.26s |
| M15 | `query.py` | identifier boost removed | killed | 1 failed, 3 passed in 0.87s |
| M16 | `dense.py` | dense auto-enables without the opt-in flag | killed | 1 failed in 0.41s |
| M17 | `dense.py` | missing table/model reported as available | killed | 1 failed in 0.32s |
| M18 | `dense.py` | requested-but-unavailable warning repeats every query | killed | 1 failed, 1 passed in 0.31s |
| M19 | `query.py` | dense rerank sign inverted | killed | 1 failed, 8 passed in 0.45s |

Operators used: constant change, comparison/boolean inversion, shifted bit width,
disabled guard, removed boost. This is a targeted set, not exhaustive mutation of every
line; the score must be read as 'these semantic changes are caught'.
