# STATE â€” Ä‘iá»u phá»‘i sá»­a 8 lá»—i blackbox

Cáº­p nháº­t sau Má»–I bÆ°á»›c. Náº¿u máº¥t ngá»¯ cáº£nh: Ä‘á»c file nÃ y trÆ°á»›c, tiáº¿p tá»¥c tá»« dÃ²ng "BÆ°á»›c hiá»‡n táº¡i".

## BÆ°á»›c hiá»‡n táº¡i

- BÆ°á»›c 4/8 XONG: Ä‘Ã£ spawn A, B, C, D (song song) lÃºc 19:2x. E sáº½ spawn sau khi má»™t nhÃ¡nh xong.
- Commit ná»n: `8690dfb` "docs: freeze FIX_SPEC/FIX_BRIEFS and start fix/STATE.md" trÃªn `master`; tree CLEAN.
- Task board: `task-1`=A, `task-2`=B, `task-3`=C, `task-4`=D (sub tá»± claim).

## Báº£ng nhÃ¡nh

| nhÃ¡nh | sub Ä‘Ã£ spawn? | tráº¡ng thÃ¡i | commit cuá»‘i | Ä‘Ã£ merge? | ghi chÃº |
|---|---|---|---|---|---|
| A (lá»—i 3â†’1â†’2) | **rá»“i** (`fix-a`) | Ä‘ang cháº¡y | â€” | chÆ°a | worktree `D:\Skill_tulan\wt-A`, cáº§n rebuild index |
| B (lá»—i 4) | **rá»“i** (`fix-b`) | Ä‘ang cháº¡y | â€” | chÆ°a | worktree `D:\Skill_tulan\wt-B` |
| C (lá»—i 5+7) | **rá»“i** (`fix-c`) | Ä‘ang cháº¡y | â€” | chÆ°a | worktree `D:\Skill_tulan\wt-C` |
| D (lá»—i 6) | **rá»“i** (`fix-d`) | Ä‘ang cháº¡y | â€” | chÆ°a | worktree `D:\Skill_tulan\wt-D` |
| E (lá»—i 8) | chÆ°a | chá» (spawn sau khi má»™t nhÃ¡nh xong) | â€” | chÆ°a | worktree `D:\Skill_tulan\wt-E` |
| verify (Ä‘á»™c láº­p) | chÆ°a | chÆ°a báº¯t Ä‘áº§u | â€” | â€” | chá»‰ spawn sau khi merge háº¿t |

## MÃ´i trÆ°á»ng Ä‘Ã£ dá»±ng (bÆ°á»›c 3)

- NhÃ¡nh chÃ­nh cá»§a repo lÃ  **`master`** (khÃ´ng pháº£i `main` nhÆ° FIX_SPEC ghi) â†’ rebase/merge vÃ o `master`.
- ÄÆ°á»ng dáº«n index/ledger **khÃ´ng cá»‘ Ä‘á»‹nh**, Ä‘Ã£ cÃ³ biáº¿n mÃ´i trÆ°á»ng sáºµn trong code:
  - `ARM_REPO_ROOT` â†’ gá»‘c repo; `ARM_DATA_DIR` â†’ thÆ° má»¥c data; index = `<data>/index.sqlite`
    (`src/ardupilot_research_mcp/config.py:12-22`) â†’ má»—i worktree tá»± dÃ¹ng index cá»§a mÃ¬nh, khÃ´ng cáº§n sá»­a src.
  - `GOVERNOR_HOME` â†’ thÆ° má»¥c chá»©a `ledger.sqlite` (`research/governor.py:60-62`).
  - VÃ¬ váº­y KHÃ”NG thÃªm `ARDU_MCP_INDEX`/`ARDU_MCP_LEDGER`: Ä‘Ã£ cÃ³ cÆ¡ cháº¿ tÆ°Æ¡ng Ä‘Æ°Æ¡ng, khÃ´ng cáº§n sá»­a src.
- 5 worktree: `D:\Skill_tulan\wt-{A,B,C,D,E}`, nhÃ¡nh `fix/{A..E}`, base `7fe0382`.
- Má»—i worktree: `data/index.sqlite` **báº£n sao riÃªng** 123,1 MB; `data/corpus` vÃ  `research/cache`
  lÃ  junction (chá»‰ Ä‘á»c) trá» vá» repo gá»‘c; ledger riÃªng (chÆ°a cÃ³ file â†’ governor táº¡o má»›i).
- Kiá»ƒm chá»©ng: `wt-B` in `index_path: D:\Skill_tulan\wt-B\data\index.sqlite`,
  `{"sources":7,"documents":4908,"chunks":65509,"params":230,"mavlink_msgs":397,"mavlink_enums":2367}`.
- Baseline master: `python -m pytest -q` â†’ `80 passed in 24.22s`.
- `tests/blackbox_cases.md` SHA-256 = `1b53e693441339207c5f770113f1f6d08b7002ebefb618d3ce73b99a58dcaf27` (khá»›p).
- Sandbox: lá»‡nh cáº§n pipe stdio (`scripts/blackbox_run.py`, `scripts/smoke_stdio.py`) pháº£i cháº¡y á»Ÿ
  cháº¿ Ä‘á»™ `danger-full-access`; pytest bÃ¬nh thÆ°á»ng cháº¡y Ä‘Æ°á»£c.

