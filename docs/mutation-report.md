# Mutation report

- selected mutants: **15** (hand-written semantic changes)
- killed: **14**
- survived: **1**
- errors: 0
- score: **0.933** (target 0.90)

**Target met** (>= 0.90).

| mutant | file | change | result | detail |
|---|---|---|---|---|
| M01 | `cite.py` | cite_id length changes | killed | 1 failed, 2 passed in 0.26s |
| M02 | `cite.py` | channel rule inverted | killed | 1 failed, 2 passed in 0.30s |
| M03 | `cite.py` | quote verification inverted | killed | 1 failed, 3 passed in 0.29s |
| M04 | `decoders/crsf.py` | wrong CRC polynomial | killed | 1 failed in 0.17s |
| M05 | `decoders/crsf.py` | CRC bit test inverted | killed | 1 failed in 0.24s |
| M06 | `decoders/crsf.py` | microsecond conversion off by one | killed | 1 failed, 2 passed in 0.18s |
| M07 | `decoders/crsf.py` | channel bit width wrong | killed | 1 failed, 2 passed in 0.16s |
| M08 | `decoders/crsf.py` | sync detection inverted | killed | 1 failed, 1 passed in 0.21s |
| M09 | `decoders/ihex.py` | checksum sign dropped | killed | 1 failed, 4 passed in 0.21s |
| M10 | `decoders/ihex.py` | length check inverted | killed | 1 failed, 4 passed in 0.18s |
| M11 | `safety.py` | hard safety rule demoted | killed | 1 failed, 8 passed in 0.18s |
| M12 | `safety.py` | dangerous verdict over-triggered | killed | 1 failed, 6 passed in 0.23s |
| M13 | `paths.py` | path containment inverted | killed | 1 failed, 6 passed in 0.27s |
| M14 | `query.py` | stopword filter removed | killed | 1 failed in 0.30s |
| M15 | `query.py` | identifier boost removed | SURVIVED | 10 passed in 0.45s |

Operators used: constant change, comparison/boolean inversion, shifted bit width,
disabled guard, removed boost. This is a targeted set, not exhaustive mutation of every
line; the score must be read as 'these semantic changes are caught'.
