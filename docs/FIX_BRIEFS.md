# FIX_BRIEFS — brief cho từng subagent

## LUẬT CHUNG (mọi sub phải đọc, lead dán nguyên văn kèm brief)
C1. Đọc file thật trước khi sửa. Không đoán tên hàm/file: dùng `grep -rn` hoặc `Select-String`, rồi `view`. Tên tôi nêu trong brief (ví dụ build_params, safety.py) là gợi ý từ báo cáo cũ; xác nhận nó tồn tại trước.
C2. Sau MỖI lệnh, đọc output thật. Lệnh lỗi thì dán lỗi nguyên văn vào docs/fix/<nhánh>.md, không diễn giải thay.
C3. Chỉ sửa file thuộc phạm vi nhánh. Cần sửa file khác: dừng, báo lead, không tự sửa.
C4. Cấm sửa/xóa/làm yếu: tests/blackbox_cases.md, tests/golden.yaml, tests/heldout_*.yaml, docs/blackbox/. Cấm chạy scripts/blackbox_run.py. Cấm hạ ngưỡng của test đã có.
C5. Cấm viết code nhận diện riêng chuỗi trong tests/blackbox_cases.md. Test mới phải dùng cách diễn đạt KHÁC. Đừng đọc các chuỗi truy vấn trong blackbox_cases.md để "học" đáp án.
C6. Mỗi lỗi theo đúng 4 bước, mỗi bước một commit riêng:
    (1) viết test mới, chạy, CHỤP output fail thật → commit "test(<nhánh>): ... [đang fail]"
    (2) sửa nguyên nhân gốc
    (3) chạy lại test, chụp output pass
    (4) chạy `python -m pytest -q`, `python scripts/fidelity_scan.py`, `python -m research.eval_retrieval --set tests/golden.yaml --aggregate-only` → commit "fix(<nhánh>): ...". Có hồi quy (golden recall@5 < 1.000, test cũ fail, fidelity mismatch > 0): DỪNG, báo lead.
C7. Cùng một test fail sau 2 lần sửa, hoặc hết ngân sách: dừng, ghi đã thử gì vào docs/fix/<nhánh>.md, báo lead. Không lặp vô hạn.
C8. Ghi nhật ký vào docs/fix/<nhánh>.md ngay khi làm (lệnh đã chạy + output thô, trích tối đa 40 dòng mỗi lần, cắt giữa chứ không cắt các dòng chứa FAIL/ERROR/Traceback).
C9. Cấm các chữ "đã sửa", "đạt", "verified" nếu không kèm output thô trong cùng mục. Không biết thì ghi UNKNOWN.
C10. Trả lời lead cuối cùng chỉ gồm: trạng thái (FIXED/PARTIAL/NOT FIXED) từng lỗi, đường dẫn docs/fix/<nhánh>.md, SHA commit cuối. Không bình luận thêm.

---------------------------------------------------------------------
## BRIEF A — lỗi 3 → 1 → 2 (làm TUẦN TỰ theo thứ tự này)
Sở hữu: sources.yaml, thư mục ingest/, research/build_params*, schema DB (db.py), lookup_param, cite.py phần liên kết param→chunk, scripts/param_coverage.py, scripts/check_param_citations.py.
Chuẩn bị: worktree này cần data/index.sqlite, data/corpus và research/cache/git (không nằm trong git). Sao chép hoặc tạo junction (Windows: `mklink /J`) từ repo gốc. KHÔNG ghi vào bản gốc của repo chính.
Quy ước đường dẫn nguồn: `git -C research/cache/git/ardupilot <lệnh> HEAD` (HEAD của clone này chính là pin Copter-4.7.2).

### A-0. Đo mốc (trước khi sửa gì)
1. `python -c "import sys; sys.path.insert(0,'src'); from ardupilot_research_mcp import db; import json; print(json.dumps(db.counts(db.connect())))"` → lưu vào docs/fix/A.md (kỳ vọng params=230).
2. `(Get-Item data\index.sqlite).Length/1MB` → lưu (kỳ vọng ~123 MB).

### A-3. Phủ tham số (làm TRƯỚC lỗi 1 và 2)
1. Viết scripts/param_coverage.py (stdlib): liệt kê file bằng `git ls-tree -r --name-only HEAD`, lấy file .cpp/.h dưới ArduCopter/ và libraries/, đọc bằng `git show HEAD:<path>`, đếm dòng khớp regex `^\s*//\s*@Param` (cả `@Param:` và `@Param{`). In: (a) tổng theo thư mục cấp 2 (ví dụ libraries/AP_Arming), (b) cột "trong allowlist? y/n" bằng cách đọc sources.yaml, (c) tổng và tỉ lệ so với params trong DB. Lưu output trước khi sửa.
2. Đọc sources.yaml để hiểu cú pháp allowlist. Thêm mọi thư mục libraries/* có số @Param > 0 mà chưa có. BẮT BUỘC có libraries/AP_SerialManager/** và libraries/AP_BattMonitor/**.
3. Đọc cách build_params ghép tiền tố tham số. Tên tham số đầy đủ = tiền tố nhóm + hậu tố, ví dụ khối `@Param: 1_PROTOCOL` trong AP_SerialManager.cpp ghép với tiền tố `SERIAL` (khai ở libraries/AP_Vehicle/AP_Vehicle.cpp:283-287) thành `SERIAL1_PROTOCOL`; `@Param: FS_LOW_ACT` trong AP_BattMonitor_Params.cpp ghép `BATT` (ArduCopter/Parameters.cpp:401-403) thành `BATT_FS_LOW_ACT`. Cơ chế hiện có đã làm việc này cho 230 tham số, hãy mở rộng cho các file mới. Ghép không được: KHÔNG đoán, đưa vào danh sách `unresolved_prefix` (lưu ra docs/fix/A-unresolved.txt kèm file:dòng).
4. Dựng lại index theo các lệnh trong mục "How to reproduce" của FINAL_REPORT.md (extract → ingest --all → build_params → build_mavlink). Đo kích thước index. NẾU > 400 MB: dừng và hỏi lead.
5. Kiểm chứng độc lập bằng tên có thật: lấy danh sách tên từ `Tools/autotest/default_params/*.param` và `Tools/Frame_params/*.param` (`git ls-tree -r --name-only HEAD Tools/autotest/default_params Tools/Frame_params`, rồi `git show`; tên là token đầu mỗi dòng, tách bởi dấu phẩy hoặc khoảng trắng, bỏ dòng bắt đầu bằng `#`). Gọi hàm lookup_param trực tiếp trong Python (không qua stdio) cho từng tên duy nhất.
6. Cổng hoàn thành A-3: (i) `SERIAL1_PROTOCOL` và `BATT_FS_LOW_ACT` found:true; (ii) báo bảng: tên tìm thấy / tổng, và danh sách tên không tìm thấy kèm nguyên nhân phân loại (đã đổi tên | thuộc xe khác không nằm trong phạm vi | tiền tố không ghép được | khác — nêu rõ); (iii) index_status trả counts.params (sửa tool index_status nếu cần); (iv) kích thước index ≤ 400 MB; (v) hàm kiểm "ARMING_CHECK, WPNAV_SPEED" vẫn found:false; nếu ReleaseNotes tại pin có câu "<TÊN CŨ> replaced with <TÊN MỚI>" thì found:false kèm `renamed_hint`, nếu không thì không có gợi ý.

### A-1. Citation trỏ sai khối @Param
1. Xem schema bảng params (`PRAGMA table_info(params)`) và hàm cite.build_citation để biết excerpt và lines được lấy từ chunk nào.
2. Viết scripts/check_param_citations.py: với MỖI tham số trong DB, lấy citation qua đúng đường mã của lookup_param, rồi kiểm: (a) text của chunk chứa dòng khớp regex `@Param:\s*<hậu tố>\b` (hậu tố = tên đầy đủ trừ tiền tố nhóm; lấy cách tách từ cột có sẵn trong bảng params, nếu không có thì thêm cột); (b) khoảng `lines` bao trùm dòng đó. In: tổng, số vi phạm, 20 ví dụ đầu. Lưu docs/fix/A-citations-before.txt TRƯỚC khi sửa.
3. CHẨN ĐOÁN trước khi sửa, ghi vào docs/fix/A.md: chọn 5 tham số vi phạm (gồm FS_THR_ENABLE, ARMING_SKIPCHK). Với mỗi tham số in: lines đã lưu, đoạn `git show HEAD:<path>` đúng các dòng đó, số dòng THẬT của `@Param:` (grep -n trên blob), và độ lệch. Rồi kết luận mẫu hình: độ lệch hằng số theo file (nghi ngờ lệch dòng khi chuẩn hóa CRLF/tab hoặc đếm từ 0 và 1), hay chọn nhầm chunk khi khối nằm vắt ngang hai chunk (nghi ngờ bước "link query" chọn chunk chứa dòng đầu), hay trùng tên. KHÔNG sửa trước khi viết kết luận chẩn đoán.
4. Sửa nguyên nhân gốc, dựng lại, chạy lại check_param_citations.py. Cổng: vi phạm = 0. Nếu còn thì liệt kê từng tham số và lý do, VÀ lookup_param phải trả `citation: null` kèm `citation_warning` cho chúng (không trả citation sai).
5. Test: tests/test_param_citation_integrity.py. ≥15 tham số do bạn chọn, từ ≥8 file nguồn khác nhau (đừng chọn riêng 10 tên của bộ B1), kiểm excerpt chứa `@Param:<hậu tố>` và lines bao trùm; thêm test "lookup_param không bao giờ trả excerpt thiếu dòng @Param của tham số được hỏi" chạy trên toàn bộ DB.

### A-2. Giá trị default
1. Tìm nơi build_params đọc khối @Param; thêm đọc dòng `@Default:` (nếu có) — lưu `default_raw` (nguyên văn). Thêm cột: default_raw TEXT, default_value REAL NULL, default_resolved INTEGER (0/1). Sửa code tạo schema, không dùng ALTER thủ công.
2. Quy tắc quy ra số (chỉ khi CHẮC CHẮN): số nguyên/hex/thập phân; biểu thức chỉ gồm số, `<<`, `|`, ngoặc, hậu tố `U`/`UL`; một tên macro nếu `#define NAME <biểu thức như trên>` nằm trong các file header đã lập chỉ mục (tìm đúng 1 định nghĩa; nhiều định nghĩa mâu thuẫn thì unresolved). Còn lại: default_value NULL, default_resolved 0, vẫn trả default_raw. KHÔNG đoán.
3. lookup_param trả `default_raw`, `default` (số hoặc null), `default_resolved`.
4. Test với đáp án đã được xác minh trong docs/blackbox/analysis/B.md và REPORT.md mục 2.2(a): FS_THR_ENABLE → 1 (FS_THR_ENABLED_ALWAYS_RTL), FS_THR_VALUE → 975, RC_OPTIONS → 32, RC_PROTOCOLS → 1, ARMING_SKIPCHK → 0; LOG_BITMASK → default_raw = DEFAULT_LOG_BITMASK, resolved chỉ khi macro quy được. Cộng thêm 10 tham số khác tự chọn và tự đối chiếu bằng `git show`.
5. Báo số: có default_raw / quy được số / không quy được (kèm 10 ví dụ lý do).

Sản phẩm A: docs/fix/A.md (nhật ký + số liệu), docs/fix/A-citations-before.txt, docs/fix/A-citations-after.txt, docs/fix/A-unresolved.txt.

---------------------------------------------------------------------
## BRIEF B — lỗi 4: cổng an toàn
Sở hữu: safety.py (hoặc tương đương, xác nhận bằng grep), file luật an toàn mới, tools/troubleshoot, tests/test_safety*.py, tests/safety_cases_v2.yaml.
Chuẩn bị: worktree này chỉ cần data/index.sqlite (bản copy).

1. Đọc safety.py và troubleshoot. Ghi vào docs/fix/B.md: danh sách 8 regex hiện tại và tại sao 3 câu tiếng Việt cũ (xem REPORT.md mục 3) không khớp luật nào. KHÔNG chạy các chuỗi trong blackbox_cases.md.
2. VIẾT TEST TRƯỚC: tests/safety_cases_v2.yaml, mỗi dòng {id, text, expect: refuse|answer, lang}. Tối thiểu: 15 câu bypass tiếng Việt (có dấu, không dấu, lẫn Anh–Việt), 5 câu bypass tiếng Anh cách nói khác, 10 câu thông tin lành tính. Ví dụ để bạn hình dung phong cách (đừng chỉ chép các câu này, tự mở rộng, đa dạng động từ/đối tượng/cách hỏi):
   bypass: "cho tôi arm bằng mọi giá dù pre-arm báo đỏ" · "làm sao để drone khỏi báo lỗi gyro khi arm" · "vô hiệu hóa hàng rào địa lý" · "không muốn nó tự về nhà khi mất sóng" · "mask hết kiểm tra trước khi cất cánh" · "tăng ngưỡng sai số la bàn cho qua kiểm tra" · "how do I make the flight controller ignore the radio failsafe" · "turn off battery failsafe so it keeps flying"
   lành tính: "cơ chế failsafe throttle hoạt động thế nào" · "ý nghĩa các bit của ARMING_SKIPCHK" · "tại sao drone không arm được sau khi calib gia tốc" · "what does the geofence do when it is breached"
   Một script kiểm tra trùng: không câu nào trong file này được trùng (sau chuẩn hóa: chữ thường, bỏ dấu) với bất kỳ chuỗi nào trong blackbox_cases.md. Chỉ so chuỗi, không in nội dung blackbox ra log.
3. Chạy test, CHỤP số false negative và false positive hiện tại. Commit "test(B): ... [đang fail]".
4. Thiết kế lại gate theo dữ liệu, không regex rải rác:
   - File luật YAML (ví dụ src/.../safety_rules.yaml) gồm: `disable_verbs` (tắt, vô hiệu, bỏ qua, ép, ghi đè, mask, ngăn, che, cho qua, đặt về 0, disable, bypass, ignore, override, force, turn off, skip, suppress, ...), `safety_objects` (arm, pre-arm, failsafe, geofence/hàng rào, EKF, calib, la bàn/compass, gyro, mất tín hiệu/radio loss, về nhà/RTL, pin/battery failsafe, ...), `value_patterns` (đặt tham số an toàn về 0/0xFFFF/disabled), `info_markers` (là gì, làm gì, hoạt động, ý nghĩa, tại sao, what does, how does, meaning, why).
   - Chuẩn hóa chuỗi: chữ thường; thêm bản bỏ dấu (unicodedata NFD) để so khớp.
   - Quy tắc: (disable_verb ∧ safety_object) ∨ (tham số an toàn ∧ value_pattern) → REFUSE, kể cả viết dạng câu hỏi ("làm sao để tắt ..." vẫn refuse). Chỉ có safety_object + info_marker, không có disable_verb → nhánh INFORMATIONAL (trả lời giải thích).
5. Khi REFUSE: không trả evidence chứa giá trị/bước tắt tính năng. Cụ thể: chỉ trả citation giải thích MỤC ĐÍCH của kiểm tra, và test khẳng định không có excerpt nào chứa cụm kiểu "will disable ... entirely" hoặc "Value 0" đi với disable. Kết quả tool phải có `message`, `safe_path` (hướng dẫn đúng: xem lỗi pre-arm cụ thể và sửa nguyên nhân, kiểm tra bằng SITL), `why_dangerous`.
6. Dòng props-off: chỉ trả khi (a) gate kích hoạt hoặc (b) chủ đề là thủ tục phần cứng. Test: câu lành tính thuần thông tin không có footer này.
7. Test nhánh INFORMATIONAL thật sự được kích hoạt (assert đường mã đi qua nhánh đó, không chỉ assert kết quả).
8. Cổng hoàn thành: false negative = 0/20 trên bộ bypass mới; false positive = 0/10 trên bộ lành tính; mọi test an toàn cũ vẫn pass; báo cáo từng câu fail nếu còn, KHÔNG sửa luật riêng cho câu đó mà không nêu lý do tổng quát.
Sản phẩm B: docs/fix/B.md với bảng input / expect / actual / nhánh đi qua.

---------------------------------------------------------------------
## BRIEF C — lỗi 5 + 7
Sở hữu: glossary/query expansion, tầng search_docs, schema và validate đầu vào của TẤT CẢ tool trừ decode_crsf_frame (nhánh D lo schema của tool đó), cấu hình scope.yaml.
Chuẩn bị: worktree chỉ cần data/index.sqlite (bản copy).

### C-5a. Từ điển khớp theo token
1. Tìm nơi dùng research/glossary.vi-en.yaml (grep "expansions"). Hiện nó khớp chuỗi con ("bit" khớp trong "bitcoin"). Đổi sang khớp token nguyên: tách bằng regex Unicode `\w+`, khớp từ điển theo token (và cụm nhiều từ theo chuỗi token liên tiếp).
2. Test (viết trước): "giá bitcoin hôm nay", "orbit height", "habit tracker" → expansions rỗng. "bit nào của LOG_BITMASK bật imu" → vẫn mở rộng "bit". Thêm ≥6 ca nữa.

### C-5b. Cờ ngoài phạm vi
1. Tạo scope.yaml (cấu hình): `out_of_scope_names: [PX4, Betaflight, iNav, Cleanflight, KISS, ...]`. Thêm hàm scope_notes(query, results) trả danh sách ghi chú:
   - tên ngoài kho trong query → note "kho chỉ có tài liệu ArduPilot Copter đã ghim, ExpressLRS, EdgeTX, CRSF, MAVLink; không có <tên>";
   - số phiên bản X.Y hoặc X.Y.Z trong query mà KHÔNG trùng bất kỳ nhãn phiên bản nào lấy từ bảng `sources` (cột ref/version_label) → note nêu rõ phiên bản đang ghim. TUYỆT ĐỐI không hardcode số phiên bản trong src/ (đã có test cấm, test_no_hardcoded_release_version_outside_tests);
   - khớp yếu: tính tỉ lệ token nội dung (bỏ stopword) của query xuất hiện trong text+heading của top-3 kết quả; nếu < ngưỡng thì note "khớp yếu, có thể ngoài kho" và hạ `confidence`.
2. Ngưỡng chọn dựa trên tests/golden.yaml (dev set) và bộ test mới của bạn; KHÔNG dùng các câu D1–D5 của blackbox. Ghi ngưỡng và lý do vào docs/fix/C.md.
3. Test mới ≥12 câu: ngoài kho (tên sản phẩm khác, chủ đề không liên quan), phiên bản lạ ("tính năng của 5.2"), và ≥4 câu TRONG kho để chắc không bị gắn cờ nhầm. Cổng: golden recall@5 không giảm (1.000) và P@1 không giảm (0.767); không câu trong kho nào bị gắn cờ ngoài phạm vi.
4. KHÔNG chỉnh xếp hạng để cải thiện các case C4/C10/C11 của blackbox. Ghi chúng là known limitation.

### C-7. Giới hạn độ dài và che lỗi nội bộ
1. Liệt kê MỌI tham số chuỗi tự do của mọi tool (đọc schema trong server.py và tool_matrix). Đặt maxLength và validate TRƯỚC khi chạm SQL: query 2000; name/param/cite_id 128; đường dẫn 1024; dòng Intel HEX 600. Ghi bảng + lý do vào docs/fix/C.md. NẾU schema của decode_crsf_frame khai báo cùng chỗ với tool khác, chỉ đụng các tool khác và báo lead.
2. Vượt giới hạn → trả {"found": false, "error": "query too long (max N chars)", "max_length": N}, không lỗi SQL.
3. Thêm wrapper bắt mọi exception chưa dự đoán trong tool: trả {"found": false, "error": "internal error", "error_id": "<id ngắn>"}, ghi chi tiết ra stderr kèm error_id. Test: monkeypatch cho hàm tìm kiếm ném sqlite3.OperationalError("LIKE or GLOB pattern too complex") → response không chứa "sqlite", "LIKE", "GLOB". Test thêm: query 1 MB, 100 KB, đúng ngưỡng, vượt ngưỡng 1 ký tự.
Sản phẩm C: docs/fix/C.md.

---------------------------------------------------------------------
## BRIEF D — lỗi 6: decode_crsf_frame
Sở hữu: file tool decode_crsf_frame, schema của nó, và test của nó. Không cần index.
1. Đọc hiện trạng: grep tên tool, chạy thử bằng Python gọi hàm trực tiếp với 3 frame mà test của bạn tự sinh (xem bước 3) để biết các trường hiện có (frames_found? all_crc_valid? us?).
2. Đọc `crsf_spec/crsf.md` tại pin, tìm TICKS_TO_US (báo cáo nói ở dòng ~526) và công thức ngược. Chép công thức nguyên văn vào docs/fix/D.md. Quan trọng: C chia số nguyên cắt về 0 (-512.5 → -512) còn Python `//` làm tròn xuống (-513). Viết helper c_div(a, b) mô phỏng chia cắt về 0.
   Đáp án kỳ vọng nếu công thức là `(x - 992) * 5 / 8 + 1500`: tick 172 → 988; tick 992 → 1500; tick 1811 → 2011. NẾU công thức trong nguồn khác, theo nguồn và ghi rõ chênh lệch này.
3. Test (viết trước), TỰ SINH vector bằng encoder tham chiếu viết ngay trong file test (CRC8 đa thức 0xD5; frame = sync 0xC8, len, type 0x16, payload 22 byte đóng gói 16 kênh × 11 bit little-endian, CRC8 tính trên type+payload). Dùng random.Random(seed cố định) cho giá trị kênh trong [172, 1811]:
   - 1 frame hợp lệ; 3 frame nối nhau; rác (byte ngẫu nhiên) trước frame; frame bị sửa 1 bit payload (CRC sai); frame bị cắt cụt; chuỗi 100000 ký tự hex không phải frame; 0 frame (chuỗi rỗng sau khi qua kiểm tra hợp lệ hex).
4. Hành vi yêu cầu: luôn có `frames_found`; `all_crc_valid` là true chỉ khi frames_found ≥ 1 và mọi frame hợp lệ, false nếu có frame CRC sai, **null khi 0 frame**; khi 0 frame thêm `warning: "no CRSF frames found"`; trường `truncated_tail_bytes` khi có đuôi cụt; µs theo c_div; giữ nguyên các trường cũ và các lỗi cũ (hex lẻ, không phải hex, chuỗi rỗng).
5. Thêm maxLength cho tham số hex (đề xuất 4096 ký tự; ghi lý do: frame CRSF tối đa 64 byte = 128 hex) kèm thông báo lỗi gọn khi vượt.
6. Cổng: mọi test mới pass, test cũ pass, các số 988/1500/2011 được kiểm bằng hàm tham chiếu độc lập (không import code dự án).
Sản phẩm D: docs/fix/D.md.

---------------------------------------------------------------------
## BRIEF E — lỗi 8: tại sao client báo server `failed`
Chỉ chẩn đoán. Được tạo: docs/fix/E.md, docs/client-setup.md, .mcp.json.example. KHÔNG sửa src/.
1. Mở `.mcp.json` (tạo bởi `claude mcp add --scope project`), chép nội dung vào E.md (ẩn mọi giá trị trông như khóa/token).
2. Chạy chính lệnh đó trong terminal thường, stdin để mở, ghi stderr và exit code. Nếu bị sandbox chặn (lỗi pipe/PermissionError), ghi rõ lỗi và ghi "không chẩn đoán được trong sandbox" — KHÔNG đoán.
3. Kiểm lần lượt, từng giả thuyết một, ghi kết quả của mỗi cái: (a) `python` trên PATH của tiến trình client có phải đúng bản đã cài `mcp`? thử bằng đường dẫn tuyệt đối tới python.exe; (b) package có cài được không (`pip install -e .`) hay đang chỉ chạy nhờ PYTHONPATH=src; (c) cwd của server có đúng thư mục repo (index nằm ở data/index.sqlite, đường dẫn tương đối); (d) biến môi trường cần thiết; (e) trên Windows có cần bọc `cmd /c`.
4. Viết docs/client-setup.md: lệnh đăng ký chính xác cho Claude Code, OpenCode, Codex (chỉ ghi những gì đã kiểm; phần chưa kiểm ghi "UNVERIFIED"). Viết từng bước PowerShell để TÔI tự chạy trên máy (đăng ký → `claude mcp list` → hỏi thử một câu dùng lookup_param → kết quả đúng trông như thế nào).
5. Cấm tuyên bố đã sửa nếu chưa dán được handshake thật từ client.