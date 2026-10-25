# STATE — điều phối sửa 8 lỗi blackbox

Cập nhật sau MỖI bước. Nếu mất ngữ cảnh: đọc file này trước, tiếp tục từ dòng "Bước hiện tại".

## Bước hiện tại

- Bước 3/8 XONG (môi trường đã dựng) — đang CHỜ lead người dùng trả lời "ok" để spawn A–D.
- Commit nền: `7fe0382` (master), working tree **bẩn**: `docs/FIX_SPEC.md`, `docs/FIX_BRIEFS.md`
  untracked (do người dùng đưa) + `docs/fix/STATE.md` (file này). Chưa commit — chờ "ok".

## Bảng nhánh

| nhánh | sub đã spawn? | trạng thái | commit cuối | đã merge? | ghi chú |
|---|---|---|---|---|---|
| A (lỗi 3→1→2) | chưa | chưa bắt đầu | — | chưa | worktree `D:\Skill_tulan\wt-A`, cần rebuild index |
| B (lỗi 4) | chưa | chưa bắt đầu | — | chưa | worktree `D:\Skill_tulan\wt-B` |
| C (lỗi 5+7) | chưa | chưa bắt đầu | — | chưa | worktree `D:\Skill_tulan\wt-C` |
| D (lỗi 6) | chưa | chưa bắt đầu | — | chưa | worktree `D:\Skill_tulan\wt-D` |
| E (lỗi 8) | chưa | chưa bắt đầu | — | chưa | worktree `D:\Skill_tulan\wt-E`, spawn sau khi một nhánh xong |
| verify (độc lập) | chưa | chưa bắt đầu | — | — | chỉ spawn sau khi merge hết |

## Môi trường đã dựng (bước 3)

- Nhánh chính của repo là **`master`** (không phải `main` như FIX_SPEC ghi) → rebase/merge vào `master`.
- Đường dẫn index/ledger **không cố định**, đã có biến môi trường sẵn trong code:
  - `ARM_REPO_ROOT` → gốc repo; `ARM_DATA_DIR` → thư mục data; index = `<data>/index.sqlite`
    (`src/ardupilot_research_mcp/config.py:12-22`) → mỗi worktree tự dùng index của mình, không cần sửa src.
  - `GOVERNOR_HOME` → thư mục chứa `ledger.sqlite` (`research/governor.py:60-62`).
  - Vì vậy KHÔNG thêm `ARDU_MCP_INDEX`/`ARDU_MCP_LEDGER`: đã có cơ chế tương đương, không cần sửa src.
- 5 worktree: `D:\Skill_tulan\wt-{A,B,C,D,E}`, nhánh `fix/{A..E}`, base `7fe0382`.
- Mỗi worktree: `data/index.sqlite` **bản sao riêng** 123,1 MB; `data/corpus` và `research/cache`
  là junction (chỉ đọc) trỏ về repo gốc; ledger riêng (chưa có file → governor tạo mới).
- Kiểm chứng: `wt-B` in `index_path: D:\Skill_tulan\wt-B\data\index.sqlite`,
  `{"sources":7,"documents":4908,"chunks":65509,"params":230,"mavlink_msgs":397,"mavlink_enums":2367}`.
- Baseline master: `python -m pytest -q` → `80 passed in 24.22s`.
- `tests/blackbox_cases.md` SHA-256 = `1b53e693441339207c5f770113f1f6d08b7002ebefb618d3ce73b99a58dcaf27` (khớp).
- Sandbox: lệnh cần pipe stdio (`scripts/blackbox_run.py`, `scripts/smoke_stdio.py`) phải chạy ở
  chế độ `danger-full-access`; pytest bình thường chạy được.
