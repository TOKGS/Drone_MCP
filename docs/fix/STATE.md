# STATE — điều phối sửa 8 lỗi blackbox

Cập nhật sau MỖI bước. Nếu mất ngữ cảnh: đọc file này trước, tiếp tục từ dòng "Bước hiện tại".

## Bước hiện tại

- Bước 5/8 đang chạy: **D xong và đã merge** (`e1f2f9d`); E đã spawn sau khi D xong. A, B, C đang chạy.
- Commit nền: `8690dfb` (docs freeze) → `58db470` (STATE) → `4c58a4c` lỗi encoding PowerShell, đã sửa ở commit này.
- Task board: `task-1`=A, `task-2`=B, `task-3`=C, `task-4`=D (completed), `task-5`=E.

## Bảng nhánh

| nhánh | sub đã spawn? | trạng thái | commit cuối | đã merge? | ghi chú |
|---|---|---|---|---|---|
| A (lỗi 3→1→2) | **rồi** (`fix-a`) | DONE — FIXED | `31f6027` (merge `f169cd5`) | **rồi** | params 230→5089 · citation 3891→0 · default 4703 raw / 3003 số · index 183,5 MB |
| F (hồi quy A) | **rồi** (`fix-c` nhận, nhánh `fix/F` trong `wt-C`) | đang chạy: out-of-corpus gate + hạ hạng `libraries/SITL/**` | — | chưa | mục tiêu: `test_out_of_corpus` PASS lại, P@1 ≥ 0,767, recall 1.000, heldout_v3 ≥ 0,933 |
| B (lỗi 4) | **rồi** (`fix-b`) | DONE — FIXED | `dc5bcc0` (merge `67f4e80`) | **rồi** | 99 passed · audit: 5/5 refusal, mỗi refusal 1 citation mục đích |
| C (lỗi 5+7) | **rồi** (`fix-c`) | DONE — FIXED (E2E tool_matrix chưa chạy: sandbox chặn pipe) | `22b9fa8` (merge `a36790b`) | **rồi** | 117 passed · golden 1.000/0.767/0.865 · fidelity PASS |
| D (lỗi 6) | **rồi** (`fix-d`) | DONE — FIXED | `fb981a1` (merge `e1f2f9d`) | **rồi** | 84 passed · fidelity 0 mismatch · golden 1.000/0.767/0.865 |
| E (lỗi 8) | **rồi** (`fix-e`) | DONE — UNKNOWN (chỉ chẩn đoán) | `511c4bb` (merge `4d5ba12`) | **rồi** | chỉ docs; nguyên nhân đo được: pipe `PermissionError` khi spawn trong sandbox; handshake client UNVERIFIED |
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

## Quyết định của lead (ghi để không mất ngữ cảnh)

- **A xin sửa `query.py` để vá 2 hồi quy do corpus mở rộng → TỪ CHỐI** (chọn phương án b): `query.py`,
  `scope.yaml`, weak-match là phạm vi nhánh C (đã merge). Lý do ghi vào FIX_REPORT.md mục (e).
- Cho phép A thử trong write-scope của mình: loại `libraries/SITL/**` (simulator-only) khỏi corpus và
  ĐO lại golden P@1 + test ngoài kho; giữ nếu P@1 về >= 0.767 và recall@5 = 1.000, ngược lại revert.
- A phải giải thích params 230 -> 5089 (trùng lặp tiền tố theo xe hay không) trước khi merge.

## Bước 10 (sau khi người dùng cho phép sửa `query.py`)

- Merge fix/A: `f169cd5`. Master lúc này: pytest `1 failed, 127 passed` (đúng test out-of-corpus),
  fidelity `86262 / 0 PASS`, golden `1.000 / 0.733 / 0.837` — 2 hồi quy ĐÃ BIẾT, đang sửa ở nhánh F.
- Đồng bộ dữ liệu: corpus master = hợp của corpus cũ + corpus A (7 561 file / 114,9 MB);
  `data/index.sqlite` master và `wt-C` đều = index của A (183,5 MB, params 5089, chunks 86262).
- Nhánh F giao lại cho `fix-c` (chủ sở hữu `query.py`/`scope.yaml`), nhánh `fix/F` tạo từ `master`
  ngay trong `wt-C` (index mới đã có sẵn ở đó). Ngân sách 60 bước.
