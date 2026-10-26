# Decisions

One entry per kept or rejected technique: what changed, measured effect, decision. Dev is the
tunable split; held-out is measured once per configuration that is kept.

## Rung 1 (lexical), 2026-10-26

| # | technique | dev (recall / P@1 / MRR / chunk) | held-out (recall / P@1 / MRR / chunk) | decision |
|---|---|---|---|---|
| 1 | glossary growth, 45 Vietnamese phrases incl. ASCII mirrors | 0.583/0.375/0.452/0.312 to 0.708/0.396/0.512/0.312 | not measured alone | kept |
| 2 | parameter-declaration priority (params table decides the answer) | to 0.771/0.500/0.593/0.312 | not measured alone | kept |
| 3 | Vietnamese anchor relaxation (glossary-fired query needs weight 2, old rule still valid) | to 0.792/0.500/0.603/0.333 | not measured alone | kept |
| 4 | `Tools/autotest/` joins `libraries/SITL/` in the test-harness penalty; 6 more gloss terms | to 0.833/0.562/0.657/0.354 | 0.723/0.354/0.490/0.369 | kept |

Kept configuration, held-out against baseline: recall@5 +0.031, P@1 -0.015, MRR -0.003, chunk-hit
0.000, negative-pass 0.571 (floor 0.571) and 0.750 on `eval_v4_neg_vi` (floor 0.750). Golden moved
1.000/0.767/0.859 to 1.000/0.800/0.886; v3 unchanged.

Rejected:

- **Declaration priority as a fixed boost.** Swept on dev: 12 gave 0.792/0.479/0.604, 16-20 gave
  0.812/0.521/0.629, 25 gave 0.833/0.521/0.639, 30 gave 0.833/0.542/0.647, 40 matched the forced
  version. Forced ranking is scale-free and scored best on dev, so the constant was removed.
- **Anchor relaxation that replaced the old rule.** It rejected Vietnamese questions whose anchor
  weight sits between 1 and 2 and dropped golden recall to 0.967 (`G14`). The rule now ORs the two
  conditions; the defect was fixed before the rung was reported.
- **Glossary entries for bare common words** (`giá`, `thời tiết`, `nấu`): they would anchor
  out-of-scope questions and endanger the negative floors. Deliberately not added.
