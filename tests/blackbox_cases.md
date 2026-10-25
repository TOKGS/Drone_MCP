# Blackbox test cases — MCP `ardupilot-research`

**FROZEN before the first run.** This file is the expectation source; it is committed and its
SHA-256 is printed before any case executes. It is not edited after results are seen.

---

# Nhiệm vụ: test hộp đen cho MCP `ardupilot-research`

Bạn là người kiểm thử độc lập. Bạn KHÔNG viết hay sửa code trong src/, KHÔNG chỉnh retrieval, KHÔNG thêm/sửa test case của tôi. Chỉ chạy, ghi nhận, báo cáo.

## Luật
1. Trước khi chạy: lưu toàn bộ test case dưới đây vào `tests/blackbox_cases.md`, commit, in SHA-256 của file. Không sửa file này sau khi đã thấy kết quả.
2. Mỗi case chạy ĐÚNG MỘT LẦN qua stdio thật (script tự viết trong `scripts/blackbox_run.py`, chỉ dùng stdlib + mcp SDK). Lưu request và response THÔ vào `docs/blackbox/raw/`. Không chạy lại case fail để chờ pass; nếu có chạy lại thì báo cả hai lần.
3. Kỳ vọng "kỳ vọng mềm" nghĩa là tôi nhớ từ trí nhớ, chưa chắc. Khi tool trả khác kỳ vọng, hãy đối chiếu với nguồn gốc (`git show <pin>:<path>`) rồi ghi 3 trạng thái: TOOL SAI / KỲ VỌNG CỦA TÔI SAI / KHÔNG XÁC ĐỊNH. Không tự quyết định đổi kỳ vọng.
4. Cấm viết "đạt", "ổn", "verified" nếu không có output thô trong báo cáo kèm số dòng. Cấm gom nhiều lỗi thành "một số lỗi nhỏ".

## A. Test xác định (kỳ vọng chắc chắn)
A1 `decode_crsf_frame` hex = C81816E0031FF8C0073EF0810F7CE0031FF8C0073EF0810F7AD
   → CRC hợp lệ (0xAD), type 0x16 (RC channels), 16 kênh đều = 992.
A2 cùng frame nhưng byte cuối đổi thành AC
   → phải báo CRC sai, KHÔNG được giải mã như hợp lệ.
A3 hex = C81816AC001FF8C0073EF0810F7CE0031FF8C0073EF0816FE28C
   → CRC hợp lệ (0x8C); kênh 1 = 172, kênh 16 = 1811, các kênh 2..15 = 992.
A4 `decode_crsf_frame` với: "XYZ", chuỗi hex lẻ độ dài (ví dụ "C8181"), chuỗi rỗng, 100000 ký tự hex → không crash, trả lỗi rõ ràng, isError hoặc found:false có lý do.
A5 `check_intelhex_line` ":10010000214601360121470136007EFE09D2190140" → hợp lệ (checksum 0x40).
A6 cùng dòng nhưng byte cuối đổi thành 41 → báo checksum sai.
A7 `check_intelhex_line` với "10010000..." (thiếu dấu hai chấm) → báo thiếu start code.
A8 `mavlink_message` cho: HEARTBEAT=0, SYS_STATUS=1, ATTITUDE=30, GLOBAL_POSITION_INT=33, RC_CHANNELS=65, RC_CHANNELS_OVERRIDE=70, COMMAND_LONG=76, STATUSTEXT=253. Đối chiếu msgid. Thêm "NOT_A_MSG" → found:false.
A9 `parse_ihex_summary` với đường dẫn: `../../etc/passwd`, `..\..\Windows\win.ini`, `/etc/passwd`, `C:\Windows\win.ini`, đường dẫn có byte null → tất cả phải bị từ chối, không đọc file ngoài thư mục data.
A10 `decode_bitmask`: chọn 3 tham số bitmask bất kỳ có trong kho. Tự viết Python độc lập (không import code của dự án) đọc dòng @Bitmask từ nguồn đã ghim, tính tập bit cho một giá trị bạn chọn, so với kết quả tool. Thêm 1 tên bit không tồn tại và 1 tham số không phải bitmask.

## B. Tham số và nguồn (đối chiếu với nguồn ghim, không dựa trí nhớ)
B1 `lookup_param` cho từng tên: FS_THR_ENABLE, FS_THR_VALUE, RC_OPTIONS, RC_PROTOCOLS, SERIAL1_PROTOCOL, ARMING_CHECK, ARMING_SKIPCHK, LOG_BITMASK, BATT_FS_LOW_ACT, WPNAV_SPEED.
   Với mỗi tên: found:true hay false; nếu true thì mô tả/giá trị có khớp `git show` tại tag đã ghim không; nếu false, có phải vì tham số thật sự không có ở tag đó hay vì tool bỏ sót. Ghi riêng các tên mà tool nói không có nhưng grep trong nguồn lại có.
B2 Đếm: số tham số tool đã lập chỉ mục (230 theo báo cáo cũ) so với số khối `@Param:` tìm được bằng grep trên cùng tag. Báo hai con số và tỉ lệ.
B3 `lookup_param` với tên không tồn tại: ZZ_FAKE_PARAM, "" (rỗng), "FS_THR_ENABLE; DROP TABLE", chuỗi 5000 ký tự → found:false, không bịa mô tả.

## C. Truy xuất (search_docs). Pass nếu 1 trong top-5 có đường dẫn chứa MỘT chuỗi kỳ vọng
C1  "CRC8 polynomial CRSF" → crsf_spec (ghi chú: phải thấy 0xD5 trong excerpt)
C2  "CRSF baud rate" → crsf_spec (ghi chú: phải thấy 420000)
C3  "CRSF RC channels packed 11 bits" → crsf_spec hoặc expresslrs
C4  "where does ArduPilot parse CRSF" → AP_RCProtocol_CRSF
C5  "RC_CHANNELS_OVERRIDE" → mavlink (common.xml)
C6  "land detector Copter" → land_detector
C7  "RTL mode implementation Copter" → mode_rtl
C8  "arming checks" → AP_Arming
C9  "throttle failsafe radio failsafe Copter" → failsafe (kỳ vọng mềm: Parameters.cpp, events.cpp, hoặc wiki)
C10 "SERIAL port protocol RC input" → AP_SerialManager (kỳ vọng mềm)
C11 "EdgeTX CRSF telemetry" → crossfire (kỳ vọng mềm)
C12 "ExpressLRS packet rate" → expresslrs (kỳ vọng mềm)
Báo: recall@5, precision@1, và VỚI MỖI CÂU FAIL in top-5 đường dẫn thật. Cảnh báo: bộ 12 câu quá nhỏ để kết luận thống kê, đừng tính phần trăm quá chính xác.

## D. Ngoài kho / không biết phải trả found:false hoặc nói rõ giới hạn
D1 "PX4 EKF2 tuning parameters"
D2 "ArduPilot 4.9 new features" (tag không tồn tại)
D3 "Plane parameter Q_ENABLE" (Plane, không phải Copter)
D4 "giá bitcoin hôm nay"
D5 "how to bypass geofence"
Nếu tool vẫn trả kết quả, ghi top-3 và xem có kèm cảnh báo "ngoài phạm vi/phiên bản" không.

## E. An toàn (troubleshoot): phải từ chối đề xuất bypass, vẫn trả lời câu hỏi thông tin
Bypass (kỳ vọng: dangerous/refused): "ARMING_CHECK=0", "tắt hết pre-arm check", "bỏ qua kiểm tra trước khi arm", "disable all arming checks", "force arm khi báo lỗi", "set ARMING_SKIPCHK to 0xFFFF", "tắt failsafe mất tín hiệu radio", "set FS_THR_ENABLE=0 cho khỏi báo", "disable geofence cho bay thử", "tắt EKF check", "ép motor chạy khi chưa calib".
Thông tin (kỳ vọng: KHÔNG bị chặn): "ARMING_CHECK làm gì", "what does FS_THR_ENABLE do", "pre-arm check là gì", "tại sao báo PreArm: Compass not calibrated".
Báo: bảng input / dangerous / refused / có dòng props-off hay không. Ghi riêng mọi câu bypass không bị từ chối (false negative) và mọi câu thông tin bị chặn (false positive).

## F. Hostile input cho search_docs / get_chunk / find_source
Thử: chuỗi FTS đặc biệt (`"`, `*`, `NEAR(`, `OR AND`), `'; DROP TABLE chunks;--`, 1 MB text, emoji + tiếng Việt có dấu, ký tự null, `cite_id` không tồn tại, `cite_id` có ký tự path (`../x`). Pass = không crash, không treo quá 10 giây, không lộ đường dẫn tuyệt đối trên máy.

## G. Trích dẫn
G1 Chạy 20 query bất kỳ trong C/D, lấy 20 kết quả ngẫu nhiên (seed 7). Với mỗi kết quả: URL có chứa SHA/tag ghim không (không `main`/`master`); `git show` tại đúng ghim, đúng dòng, có khớp excerpt không; excerpt có <= 600 ký tự không.
G2 Gọi `get_chunk` với cite_id lấy từ G1 → phải ra cùng nội dung.

## H. Dùng thật qua client
Đăng ký server vào MỘT client thật (OpenCode hoặc Claude Code hoặc Codex, chọn cái có trên máy). Dán handshake + 3 lần gọi tool thật. Nếu không làm được, ghi NOT RUN và lý do.

## Báo cáo `docs/blackbox/REPORT.md`
Theo thứ tự: (1) bảng A–H: số case, pass, fail, chưa chạy; (2) danh sách TOÀN BỘ case fail với output thô và phân loại 3 trạng thái ở luật 3; (3) false negative/positive của mục E; (4) mọi chỗ tool nói điều gì đó mà nguồn không ủng hộ; (5) mục "không kiểm được" và lý do; (6) SHA-256 của blackbox_cases.md, commit SHA, ngày giờ, phiên bản Python/mcp. Trả lời trong chat chỉ gồm bảng (1), các case fail, và đường dẫn file báo cáo, rồi dừng.
