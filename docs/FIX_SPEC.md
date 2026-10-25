# Vai trò: LEAD điều phối sửa lỗi MCP `ardupilot-research`

Bạn là lead. Bạn KHÔNG tự sửa code trong src/. Bạn spawn subagent để sửa, bạn merge và kiểm soát.
Đọc `docs/blackbox/REPORT.md` và `docs/FIX_SPEC.md` (đặc tả lỗi 1–8). Mọi "Luật cứng" trong FIX_SPEC áp dụng cho mọi sub và cho bạn.

## Chia việc: mỗi sub một git worktree + nhánh riêng, index/ledger riêng
- Sub A: lỗi 3 → 1 → 2 (làm TUẦN TỰ trong cùng sub, vì cùng đụng ingest/schema DB/liên kết param→chunk và phải build lại index). Sở hữu: ingest/, build_params, db schema, lookup_param, sources.yaml.
- Sub B: lỗi 4 (cổng an toàn). Sở hữu: safety.py, file luật yaml, troubleshoot.
- Sub C: lỗi 5 + 7 (từ điển khớp theo token, cờ ngoài phạm vi, maxLength cho mọi tool). Sở hữu: glossary/query expansion, tầng search_docs, schema các tool.
- Sub D: lỗi 6 (decode_crsf_frame). Sở hữu: file tool đó và test của nó.
- Sub E: lỗi 8 (chẩn đoán vì sao client báo `failed`). Chỉ chẩn đoán, không sửa src/.
Nếu đường dẫn index/ledger đang bị cố định trong code, bạn tự thêm biến môi trường để mỗi worktree trỏ file riêng (commit riêng, chạy test sau đó) TRƯỚC khi spawn sub.

## Brief bạn phải đưa cho MỖI sub (sub có thể không thấy ngữ cảnh của bạn: đưa đủ, đừng giả định)
1. Nhánh, worktree, đường dẫn index/ledger riêng, số lỗi phụ trách và trích đúng phần đó trong FIX_SPEC.md.
2. Chỉ được sửa file mình sở hữu. Cần sửa file khác thì dừng và báo bạn, không tự sửa.
3. Cấm sửa/xóa: tests/blackbox_cases.md, tests/golden.yaml, tests/heldout_*.yaml, docs/blackbox/. Cấm chạy scripts/blackbox_run.py.
4. Quy trình mỗi lỗi: viết test mới (diễn đạt KHÁC bộ hộp đen) → chạy, chụp output fail thật → commit "test: ... (đang fail)" → sửa → chạy lại, chụp output pass → commit "fix: ...". Chạy toàn bộ pytest và fidelity scan sau mỗi lỗi; hồi quy thì dừng.
5. Ngân sách: tối đa [N bước / M token cho từng sub, điền]. Cùng một test fail sau 2 lần sửa, hoặc hết ngân sách: dừng và báo đã thử gì. Bạn không tự thay sub mà không hỏi tôi.
6. Sản phẩm: `docs/fix/<nhánh>.md` có trạng thái FIXED/PARTIAL/NOT FIXED, commit test-fail và fix, output thô trước/sau, số liệu FIX_SPEC yêu cầu. Cấm viết "đã sửa/đạt" nếu thiếu output thô.

## Merge
Từng nhánh một, nhánh nào xong trước (B, D, C, E thường trước; A sau cùng). Trước mỗi merge: rebase lên main, chạy pytest, fidelity scan, golden eval. Có hồi quy hoặc xung đột về nghĩa (không chỉ xung đột dòng) thì dừng và báo, không giải quyết bằng cách xóa test. Sau khi A merge: build lại index một lần, chạy lại toàn bộ test và `scripts/check_param_citations.py`.

## Kiểm chứng độc lập
Chỉ sau khi mọi nhánh đã merge, spawn MỘT sub kiểm chứng MỚI, chỉ đọc code đã merge và bộ test, KHÔNG đọc `docs/fix/*.md` trước khi chạy xong:
1. In SHA-256 của tests/blackbox_cases.md, so với `1b53e693441339207c5f770113f1f6d08b7002ebefb618d3ce73b99a58dcaf27`; không khớp thì dừng.
2. Chạy `python scripts/blackbox_run.py` đúng MỘT lần, ghi vào `docs/blackbox/run2/` (không ghi đè run1).
3. Bảng so sánh run1 → run2 cho 108 case; liệt kê riêng mọi hồi quy (pass→fail). Không sửa src/ hay test.

## Báo cáo
Tạo `docs/FIX_REPORT.md` theo mục "Bước cuối" trong FIX_SPEC, kèm: sub nào làm gì, merge lúc nào (commit SHA), mọi quyết định bạn tự đưa ra, chi phí thực tế mỗi sub nếu đo được, danh sách NOT FIXED/PARTIAL/chưa kiểm chứng.
Trả lời trong chat chỉ gồm: bảng trạng thái từng lỗi, danh sách hồi quy, mục NOT FIXED, đường dẫn FIX_REPORT.md. Rồi dừng.

Trước khi spawn sub nào: báo kế hoạch ngắn (worktree, ngân sách từng sub) và chờ tôi trả lời "ok".