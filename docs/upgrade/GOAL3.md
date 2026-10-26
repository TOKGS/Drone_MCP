Phase 3 cho ardupilot-research-mcp tại D:\Skill_tulan\ardupilot-research-mcp, branch mới `feat/phase3-vi-retrieval` tạo từ `master` (commit 235b36b trở đi): Phần A sửa lỗi vặt, Phần B thu hẹp khoảng cách tiếng Việt so với tiếng Anh bằng bộ đánh giá tiếng Việt MỚI. Chi tiết đầy đủ ở docs/upgrade/PHASE3_BRIEF.md; luật cứng, cách dùng subagent và cách báo cáo vẫn theo docs/upgrade/DEEPSEEK_BRIEF.md (phần 2, 3, 6, 11).

RÀNG BUỘC KHÔNG ĐƯỢC BỎ:
1. Đọc PHASE3_BRIEF.md và PROGRESS3.md trước mỗi lượt. Task nào chưa tick là chưa làm. Không tick khi chưa có commit và output thật.
2. Tập đóng băng không được sửa: tests/heldout_*.yaml, tests/eval_v4_*.yaml, tests/blackbox_cases.md, docs/*.sha256 hiện có, và tập held-out v5-vi sau khi khóa hash. Held-out v4 chỉ còn là chốt chặn hồi quy: tối đa MỘT lần chạy cho mỗi cấu hình được giữ, không dùng để chọn phương án. Không ai mở tập held-out v5-vi để đọc câu hỏi; chỉ chạy evaluator với --aggregate-only.
3. Người viết câu hỏi v5-vi là subagent mới, không đọc query.py, glossary, các file v4 hay output eval; câu hỏi không được là diễn đạt lại câu v4 (validator kiểm tra chồng lấn). Tuning chỉ trên dev (v5-vi dev, v4 dev).
4. Offline lúc trả lời: chỉ ingest/ và research/ được dùng mạng. chunks.text giữ nguyên văn từng byte. Không làm yếu cổng an toàn; câu an toàn tiếng Việt kiểu chat (không dấu, viết tắt) phải vẫn bị từ chối/trả lời đúng. Cổng anchor luôn chạy trước mọi đường dense.
5. Mặc định phải giữ nguyên hành vi cho tới khi đạt tiêu chí ship; cấu hình thử nghiệm đứng sau cờ. Thí nghiệm trên bản sao index, không ghi đè data/index.sqlite gốc.
6. Git: chỉ làm trên branch trên, commit nhỏ, không push, không force, không --no-verify, không commit data/ hay model. Ghi file bằng LF (đọc/ghi bytes hoặc newline="\n"); kiểm tra wc -c và git diff --stat sau khi ghi PROGRESS3.md, query.py, các file YAML.
7. Trung thực: mọi số phải dán từ output thật kèm lệnh; chưa chạy ghi NOT RUN, chưa kiểm chứng ghi UNVERIFIED. Kết quả âm được chấp nhận, che giấu thì không.

NGHIỆM THU (chỉ tính khi có output thô):
- Phần A: A1 đến A6 xong, check_readmes bắt được số test sai (có test cho nó), mọi gate xanh, mutation báo cáo đúng số thật.
- B0: >= 110 câu tiếng Việt/pha trộn, >= 40% không dấu, >= 15 negative (có loại nghe kỹ thuật nhưng ngoài phạm vi), validator 0 lỗi, hash dev/held-out đã commit, evaluator từ chối file bị sửa, baseline lưu ở docs/upgrade/baseline3/, docs/eval-v5-vi.md.
- Ship mặc định chỉ khi trên held-out v5-vi: MRR tăng >= 0.05 và recall@5 không giảm, không nhóm nào tụt quá 0.05 (nêu cỡ mẫu), và trên v4 chốt chặn: recall@5 >= 0.70, MRR >= 0.45, negative-pass >= 0.571, neg-vi >= 0.750. Không đạt thì để sau cờ và nói rõ.
- Mọi gate phần 8 của DEEPSEEK_BRIEF.md pass (pytest, fidelity, param citations, verify_citations, audit_safety, bench p95 <= 400 ms, mutation, blackbox 0 regression, safety bật/tắt dense, fallback). Báo cáo docs/upgrade/PHASE3_REPORT.md đủ 12 mục.

QUY TRÌNH: làm từng stage nhỏ, dùng subagent cho việc dài (một chủ cho mỗi file, mỗi subagent một worktree, việc dài chạy nền và đọc log); lời báo của subagent không phải bằng chứng cho tới khi chính bạn chạy lại lệnh. Làm Phần A trước, rồi B0 (bộ đo mới), rồi mới đụng retriever. Dừng và báo "READY FOR AUDIT B0" sau khi B0 đạt nghiệm thu (trước khi sửa retriever), rồi báo "READY FOR AUDIT PHASE 3" khi xong cả phần còn lại. Dừng khi lỗi lặp lại hai lần hoặc cần sửa file đóng băng, ghi lý do vào BLOCKERS thay vì báo xong.
