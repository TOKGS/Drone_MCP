# Mutation report

- selected mutants: **12** (hand-written semantic changes)
- killed: **11**
- survived: **1**
- errors: 3
- score: **0.917** (target 0.90)

**Target met** (>= 0.90).

| mutant | file | change | result | detail |
|---|---|---|---|---|
| M01 | `cite.py` | cite_id length changes | killed | 1 failed, 2 passed in 0.39s |
| M02 | `cite.py` | channel rule inverted | killed | 1 failed, 2 passed in 0.36s |
| M03 | `cite.py` | quote verification inverted | killed | 1 failed, 3 passed in 0.54s |
| M04 | `decoders/crsf.py` | wrong CRC polynomial | killed | 1 failed in 1.69s |
| M05 | `decoders/crsf.py` | CRC bit test inverted | killed | 1 failed in 1.89s |
| M06 | `?` |  | error | mutation target not found (code drift) |
| M07 | `decoders/crsf.py` | channel bit width wrong | killed | 1 failed, 2 passed in 1.79s |
| M08 | `decoders/crsf.py` | sync detection inverted | killed | 1 failed, 1 passed in 1.69s |
| M09 | `decoders/ihex.py` | checksum sign dropped | killed | 1 failed, 8 passed in 1.68s |
| M10 | `decoders/ihex.py` | length check inverted | killed | 1 failed, 8 passed in 1.68s |
| M11 | `?` |  | error | mutation target not found (code drift) |
| M12 | `?` |  | error | mutation target not found (code drift) |
| M13 | `paths.py` | path containment inverted | killed | 1 failed, 10 passed in 1.71s |
| M14 | `query.py` | stopword filter removed | SURVIVED | 27 passed in 20.55s |
| M15 | `query.py` | identifier boost removed | killed | 1 failed, 26 passed in 16.74s |

Operators used: constant change, comparison/boolean inversion, shifted bit width,
disabled guard, removed boost. This is a targeted set, not exhaustive mutation of every
line; the score must be read as 'these semantic changes are caught'.
