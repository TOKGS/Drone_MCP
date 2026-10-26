Nâng cấp ardupilot-research-mcp tại D:\Skill_tulan\ardupilot-research-mcp, branch `feat/eval-v4-hybrid-retrieval`: dựng bộ đánh giá v4 (Phase 1), rồi cải thiện retrieval và chứng minh bằng số đo (Phase 2). Chi tiết đầy đủ nằm ở docs/upgrade/DEEPSEEK_BRIEF.md; tiến độ ở docs/upgrade/PROGRESS.md.

RÀNG BUỘC KHÔNG ĐƯỢC BỎ:
1. Đọc DEEPSEEK_BRIEF.md và PROGRESS.md trước mỗi lượt. PROGRESS.md là điểm resume: task nào chưa tick là chưa làm.
2. Tập đóng băng không được sửa: tests/heldout_locked.yaml, heldout_v2.yaml, heldout_v3.yaml, tests/blackbox_cases.md, docs/heldout*.sha256, và tập held-out v4 sau khi đã khóa hash. Không ai mở tập held-out v4 để đọc câu hỏi; chỉ chạy evaluator với --aggregate-only. Không tinh chỉnh theo nó.
3. Người viết câu hỏi không được gọi code retrieval và không đọc query.py. Đáp án lấy từ corpus (data/corpus hoặc SQL trên bảng documents/chunks), không lấy từ kết quả của retriever.
4. Offline lúc trả lời: không import module mạng ngoài src/ardupilot_research_mcp/ingest/ và research/ (tests/test_offline.py kiểm tra). chunks.text giữ nguyên văn từng byte. Cổng an toàn (safety.py, safety_rules.yaml) không được làm yếu đi, và đường dense phải đi qua cùng bộ lọc trích dẫn. Câu ngoài corpus vẫn trả found:false (cổng anchor chạy trước).
5. Dense là tùy chọn: thiếu extras, model hoặc bảng chunk_vectors thì tự quay về BM25, CI trên bản clone mới vẫn xanh. Thí nghiệm chạy trên bản sao index, không ghi đè data/index.sqlite gốc.
6. Git: chỉ làm trên branch trên, commit nhỏ, không push, không force, không --no-verify, không commit data/, model, research/cache/.
7. Trung thực: mọi con số phải dán từ output thật kèm lệnh. Chưa chạy thì ghi NOT RUN, chưa kiểm chứng thì ghi UNVERIFIED. Không tick task khi chưa có commit và bằng chứng. Không báo "xong" khi còn task chưa tick.

NGHIỆM THU (chỉ tính khi có output thô):
- Phase 1: >= 120 câu, >= 40% tiếng Việt (có không dấu và pha Anh-Việt), đủ 8 nhóm, >= 10 câu ngoài phạm vi, >= 60 câu có answer_snippet; validator 0 lỗi; hai file sha256 đã commit; evaluator thoát lỗi khi tập bị sửa (chứng minh bằng test); baseline v4 đã lưu; golden và v3 vẫn ra đúng số gốc (1.000/0.767/0.859 và 0.933/0.833/0.868).
- Phase 2, ship dense mặc định chỉ khi: trên held-out v4 MRR tăng >= 0.05 và recall@5 không giảm; không nhóm nào tụt quá 0.05 recall@5 hoặc MRR; nhóm tiếng Việt tốt hơn; negative-pass-rate không giảm; golden và v3 không tụt; blackbox 0 regression; an toàn 0 false negative và 0 false positive; p95 search <= 400 ms. Không đạt thì để dense tắt mặc định (ARM_DENSE=1) và nói rõ trong báo cáo. Không đạt chỉ tiêu là kết quả chấp nhận được, che giấu thì không.
- Mọi gate ở phần 8 của brief đã chạy, output dán vào docs/upgrade/UPGRADE_REPORT.md theo đúng 11 mục.

QUY TRÌNH: làm từng stage nhỏ. Cho phép dùng subagent cho việc dài: mỗi subagent một worktree riêng, mỗi file một chủ sở hữu, việc dài chạy nền và đọc log; nhưng lời báo của subagent không phải bằng chứng cho tới khi chính bạn chạy lại lệnh. Sau mỗi stage: chạy gate liên quan, cập nhật PROGRESS.md (trạng thái, commit, lệnh, dòng output chính). DỪNG và báo "READY FOR AUDIT PHASE 1" ngay khi Phase 1 đạt nghiệm thu, chưa được tự sang Phase 2 cho tới khi chủ dự án xác nhận. Dừng khi một lỗi lặp lại hai lần, hoặc khi cần sửa file đóng băng, và ghi lý do vào mục BLOCKERS thay vì báo xong.
