# A — Kiểm chứng case xác định A1…A10

Phạm vi: 10 case A1…A10 trong `tests/blackbox_cases.md`, mở rộng thành 17 dòng kết quả (A3, A8,
A9, A10 được tách theo từng input con) + 2 file rerun đã công bố (`A1_RERUN_CORRECTED`,
`A2_RERUN_CORRECTED`) báo riêng ở §5.

## 0. Cách làm, quy ước dòng

- Nguồn duy nhất: `docs/blackbox/raw/<CASE>.json` (kết quả chạy đúng một lần, thô) và
  `tests/blackbox_cases.md` (kỳ vọng đóng băng, chỉ đọc, không sửa). Đối chiếu nguồn gốc bằng
  `git -C research/cache/git/<repo> show <pin>:<path>` tại các pin đã ghim.
- **Không gọi MCP server, không chạy lại case nào.** Hai file `*_RERUN_CORRECTED` là rerun đã được
  công bố sẵn trong raw; tôi cũng chỉ đọc file, không gọi lại tool.
- Toán độc lập: `scripts/blackbox_independent.py` (CRC8 poly 0xD5 trên Type+Payload, unpack 16×11
  bit, checksum Intel HEX bù hai, parser `@Bitmask`) + `scripts/verify_a.py` (script kiểm chứng của
  mục A, stdlib, không import code dự án). Chạy lại:
  `$env:PYTHONUTF8='1'; python scripts/verify_a.py`.
- **Quy ước dòng:** payload tool nằm trọn trong một dòng vật lý của file raw
  (`"text": "..."`). Vì vậy `raw/A3.json:27` nghĩa là *toàn bộ* payload của A3; dòng 6 là input;
  `"isError"` ở dòng 23 (A1–A9, rerun) và 25 (A10); payload A10 ở dòng 29. Mọi trích dẫn dưới đây
  là nguyên văn đoạn payload đã giải mã từ `response.content[0].text`.
- CRSF: frame 1 sync + 1 length + 1 type + 22 payload + 1 CRC = 26 byte = **52 ký tự hex**;
  16 kênh 11 bit đóng gói trong 22 byte (`crsf_spec:crsf.md:523`), CRC8 poly 0xD5 trên Type+Payload
  (`crsf_spec:crsf.md:188–190`), quy đổi tick→µs `TICKS_TO_US(x) = (x-992)*5/8+1500`
  (`crsf_spec:crsf.md:526`).

## 1. Bảng tổng hợp

| Case | Kỳ vọng (tests/blackbox_cases.md) | Kết quả thô (raw, file:dòng) | Verdict | Phân loại 3 trạng thái |
|---|---|---|---|---|
| A1 | `:19–20` CRC 0xAD, type 0x16, 16 kênh = 992 | `raw/A1.json:6` (input), `:27` (payload) | **FAIL** | KỲ VỌNG CỦA TÔI SAI |
| A2 | `:21–22` CRC sai, không giải mã như hợp lệ | `raw/A2.json:6`, `:27` | **FAIL** | KỲ VỌNG CỦA TÔI SAI |
| A3 | `:23–24` CRC 0x8C; kênh 1=172, 16=1811, 2..15=992 | `raw/A3.json:6`, `:27` | PASS | — |
| A4_XYZ | `:25` “XYZ” → không crash, lỗi rõ | `raw/A4_XYZ.json:6`, `:27` | PASS | — |
| A4_ODD | `:25` hex lẻ → không crash, lỗi rõ | `raw/A4_ODD.json:6`, `:27` | PASS | — |
| A4_EMPTY | `:25` chuỗi rỗng → không crash, lỗi rõ | `raw/A4_EMPTY.json:6`, `:27` | PASS | — |
| A4_100K | `:25` 100000 ký tự hex → không crash, lỗi rõ | `raw/A4_100K.json:6`, `:27` | PASS (ghi chú §6.2) | — |
| A5 | `:26` checksum 0x40, hợp lệ | `raw/A5.json:6`, `:27` | PASS | — |
| A6 | `:27` byte cuối 0x41 → báo checksum sai | `raw/A6.json:6`, `:27` | PASS | — |
| A7 | `:28` thiếu “:” → báo thiếu start code | `raw/A7.json:6`, `:27` | PASS | — |
| A8_HEARTBEAT…STATUSTEXT | `:29` 8 msgid + NOT_A_MSG found:false | `raw/A8_*.json:6`, `:27` | PASS (8/8 + 1) | — |
| A9 (5 đường dẫn) | `:30` cả 5 bị từ chối, không đọc ngoài `data/` | `raw/A9_*.json:6`, `:27` | PASS (5/5) | — |
| A10_RC_OPTIONS | `:31` 3 tham số bitmask tự tính bit, so tool | `raw/A10_RC_OPTIONS.json:6`, `:29` | PASS | — |
| A10_LOG_BITMASK | `:31` | `raw/A10_LOG_BITMASK.json:6`, `:29` | PASS | — |
| A10_ARMING_CHECK | `:31` | `raw/A10_ARMING_CHECK.json:6`, `:29` | **FAIL** | KỲ VỌNG CỦA TÔI SAI |
| A10_BAD_BIT | `:31` tên bit không tồn tại | `raw/A10_BAD_BIT.json:6`, `:29` | PASS | — |
| A10_NON_BITMASK | `:31` tham số không phải bitmask | `raw/A10_NON_BITMASK.json:6`, `:29` | PASS (*) | — (§3.4, §7) |

Tổng: **14 PASS, 3 FAIL** trên 17 dòng case chính; 3 FAIL đều thuộc “KỲ VỌNG CỦA TÔI SAI”,
không có bằng chứng TOOL SAI. Hai rerun công bố ở §5 không được tính vào bảng này.
(*) A10_NON_BITMASK: PASS theo hành vi trả về (found:false, không bịa bit), nhưng nhánh “tham số
tồn tại nhưng không phải bitmask” chưa được kiểm — xem §3.4 và §7.3.

## 2. Phân tích từng case FAIL (3 trạng thái)

### 2.1 A1 — FAIL — KỲ VỌNG CỦA TÔI SAI

Kỳ vọng `tests/blackbox_cases.md:19–20`: `hex = C81816E0031FF8C0073EF0810F7CE0031FF8C0073EF0810F7AD`
→ “CRC hợp lệ (0xAD), type 0x16, 16 kênh đều = 992”.
Input thô `raw/A1.json:6`: `"hex": "C81816E0031FF8C0073EF0810F7CE0031FF8C0073EF0810F7AD"` —
**đúng 51 ký tự**, giống hệt đề, và `request_jsonrpc` gửi y hệt (`identical_to_jsonrpc=True`).

Kết quả thô `raw/A1.json:27` (nguyên văn toàn bộ payload):

```json
{
  "found": false,
  "error": "odd number of hex digits"
}
```

`isError` = false (`raw/A1.json:23`). Tính độc lập: 51 là số lẻ ⇒ `bytes.fromhex` từ chối ngay
(`ValueError: non-hexadecimal number found in fromhex() arg at position 51`), không có chuỗi byte
nào để tính CRC/ticks. Nguồn ghim `crsf_spec:crsf.md:523` (16 kênh trong 22 byte payload) +
`:188–190` (CRC 8 bit) ⇒ frame 0x16 phải dài 26 byte = **52 nibble**, không thể là 51.

Dạng đúng của đề là chèn nibble `C` vào index 49: `C81816…F0810F7AD` → `C81816…F0810F7CAD`
(52 ký tự). Tính độc lập trên dạng này: type 0x16, payload 22 byte, CRC trong frame 0xAD = CRC tính
lại 0xAD, ticks 16×992 — đúng y kỳ vọng. Rerun công bố `A1_RERUN_CORRECTED` (52 ký tự) xác nhận
điều này (§5).

**Kết luận:** tool xử lý đúng (từ chối hex lẻ, y như kỳ vọng A4_ODD `:25`); lỗi nằm ở input/kỳ vọng
đóng băng bị thiếu một nibble → **KỲ VỌNG CỦA TÔI SAI**, không phải TOOL SAI.

### 2.2 A2 — FAIL — KỲ VỌNG CỦA TÔI SAI

Kỳ vọng `tests/blackbox_cases.md:21–22`: “cùng frame nhưng byte cuối đổi thành AC → phải báo CRC
sai, KHÔNG được giải mã như hợp lệ”. Vì A1 đã thiếu nibble, A2 thừa hưởng đúng lỗi đó: input thô
`raw/A2.json:6` là `"hex": "C81816E0031FF8C0073EF0810F7CE0031FF8C0073EF0810F7AC"` — 51 ký tự.
Tool trả cùng payload lỗi (`raw/A2.json:27`):

```json
{
  "found": false,
  "error": "odd number of hex digits"
}
```

Không thể kiểm CRC vì input không phải chuỗi byte; kỳ vọng “báo CRC sai” là bất khả thi trên chuỗi
51 nibble. Tính độc lập trên dạng sửa 52 ký tự (`…F0810F7CAC`): CRC trong frame 0xAC, CRC tính lại
0xAD ⇒ sai CRC. Rerun công bố `A2_RERUN_CORRECTED` cho `"crc": 172, "crc_computed": 173,
"crc_valid": false, "all_crc_valid": false` (`raw/A2_RERUN_CORRECTED.json:27`) — đúng kỳ vọng.

**Kết luận:** cùng gốc lỗi với A1 → **KỲ VỌNG CỦA TÔI SAI**, không phải TOOL SAI. Ghi chú: rerun
vẫn liệt kê channels dù CRC sai (found:true) nhưng đánh dấu `crc_valid=false`; nó không coi frame là
hợp lệ, nên không vi phạm “KHÔNG được giải mã như hợp lệ”.

### 2.3 A10_ARMING_CHECK — FAIL — KỲ VỌNG CỦA TÔI SAI

Input `raw/A10_ARMING_CHECK.json:6`: `"param": "ARMING_CHECK", "value": "6"`. Payload
(`raw/A10_ARMING_CHECK.json:29`):

```json
{
  "found": false,
  "param": "ARMING_CHECK",
  "candidates": ["_XY_IMAX","_FLOW_MAX","_FILT_HZ","_QUAL_MIN","_BRAKE_RATE","SPD_MS","SPD_HIGH_MS","ALT_LOW_M"],
  "note": "parameter not found; nothing was invented"
}
```

Đối chiếu nguồn ghim (fb77356 = tag Copter-4.7.2):
`git grep -n "ARMING_CHECK" fb77356` chỉ trả về các dòng ReleaseNotes và các định danh khác
`ARMING_CHECK_THROTTLE` (option RC, không phải tham số); **không** có `@Param:`/`@Bitmask` nào tên
ARMING_CHECK trong mã. `ArduCopter/ReleaseNotes.txt:654`:
`- ARMING_CHECK replaced with ARMING_SKIPCHK (@tpwrules, PR:31568)`. Tham số kế nhiệm:
`libraries/AP_Arming/AP_Arming.cpp:195` `// @Param: SKIPCHK`, `:198`
`// @Bitmask: 1:Barometer,2:Compass,3:GPS lock,4:INS,5:Parameters,6:RC Channels,7:Board voltage,8:Battery Level,10:Logging Available,11:Hardware safety switch,12:GPS Configuration,13:System,14:Mission,15:Rangefinder,16:Camera,17:AuxAuth,18:VisualOdometry,19:FFT`,
`:201` `AP_GROUPINFO("SKIPCHK", 13, AP_Arming, checks_to_skip, 0),`.

⇒ Tại pin **không tồn tại dòng `@Bitmask` của ARMING_CHECK** nên không thể “tính tập bit cho
ARMING_CHECK value 6” như đề yêu cầu. Nếu áp định nghĩa kế nhiệm (ARMING_SKIPCHK, dòng 198) cho
value 6 thì bits 1,2 = Barometer, Compass — nhưng đó không phải ARMING_CHECK, không được dùng để
chấm. Đề cũng tự vi phạm luật “chọn 3 tham số bitmask **có trong kho**” (`:31`).

**Kết luận:** tool trả `found:false` + “nothing was invented” là đúng với nguồn ghim; kỳ vọng chọn
một tham số không tồn tại ở pin → **KỲ VỌNG CỦA TÔI SAI**. (Kiểm phụ, không tính bằng chứng thô:
index hiện lưu tên `SKIPCHK` chứ không phải `ARMING_SKIPCHK` — xem ghi chú §7.)

## 3. Các case PASS — đối chiếu độc lập

### 3.1 A3

Input `raw/A3.json:6` = `C81816AC001FF8C0073EF0810F7CE0031FF8C0073EF0816FE28C` (52 ký tự).
Tính độc lập: 26 byte; `length`=24; type 0x16; payload 22 byte; CRC trong frame 0x8C = CRC tính lại
0x8C (hợp lệ); ticks = `[172, 992, 992, 992, 992, 992, 992, 992, 992, 992, 992, 992, 992, 992, 992, 1811]`.
Tool trả khớp từng trường (`raw/A3.json:27`):

```json
"found": true, "byte_count": 26, "frame_count": 1, "all_crc_valid": true,
"sync": 200, "length": 24, "type": 22, "type_name": "RC Channels Packed",
"payload_hex": "ac001ff8c0073ef0810f7ce0031ff8c0073ef0816fe2",
"crc": 140, "crc_computed": 140, "crc_valid": true, "channel": 1, "ticks": 172,
"channel": 16, "ticks": 1811
```

(Toàn văn payload tại `raw/A3.json:27`; các kênh 2..15 đều `"ticks": 992, "us": 1500`.)
Đúng kỳ vọng `:23–24` → PASS. Sai lệch `us` của kênh 1 (987 so với 988 theo công thức nguồn) không
thuộc kỳ vọng A3, ghi riêng §6.1.

### 3.2 A8 — 8 msgid + NOT_A_MSG

msgid độc lập lấy từ `@pin` của mavlink (`minimal.xml`, `standard.xml`, `common.xml`); tool trả
trong payload mỗi file (dòng 27):

| Message | msgid nguồn ghim (file:dòng) | tool `msgid` | raw | Khớp |
|---|---|---|---|---|
| HEARTBEAT | 0 — `minimal.xml:747` | 0 | `raw/A8_HEARTBEAT.json:27` | ✓ |
| SYS_STATUS | 1 — `common.xml:5548` | 1 | `raw/A8_SYS_STATUS.json:27` | ✓ |
| ATTITUDE | 30 — `common.xml:5733` | 30 | `raw/A8_ATTITUDE.json:27` | ✓ |
| GLOBAL_POSITION_INT | 33 — `standard.xml:117` | 33 | `raw/A8_GLOBAL_POSITION_INT.json:27` | ✓ |
| RC_CHANNELS | 65 — `common.xml:6052` | 65 | `raw/A8_RC_CHANNELS.json:27` | ✓ |
| RC_CHANNELS_OVERRIDE | 70 — `common.xml:6113` | 70 | `raw/A8_RC_CHANNELS_OVERRIDE.json:27` | ✓ |
| COMMAND_LONG | 76 — `common.xml:6182` | 76 | `raw/A8_COMMAND_LONG.json:27` | ✓ |
| STATUSTEXT | 253 — `common.xml:7280` | 253 | `raw/A8_STATUSTEXT.json:27` | ✓ |
| NOT_A_MSG | không có trong cả 3 XML | `found:false` | `raw/A8_NOT_A_MSG.json:27` | ✓ |

Tất cả `isError` = false, `resolved_by` = `"name"`, `"ref": "eec8824212c1fe8c5d8f5181fcfdef54ee219b63"`.
Đúng kỳ vọng `:29` → PASS.

### 3.3 A9 — 5 đường dẫn đều bị từ chối; không đọc file ngoài `data/`

| Input (`raw/A9_*.json:6`) | Lỗi tool trả (`:27`, nguyên văn) | `found` | Nội dung file lọt ra? |
|---|---|---|---|
| `../../etc/passwd` | `"path outside the data directory: ../../etc/passwd"` | false | không |
| `..\..\Windows\win.ini` | `"path outside the data directory: ..\\..\\Windows\\win.ini"` | false | không |
| `/etc/passwd` | `"path outside the data directory: /etc/passwd"` | false | không |
| `C:\Windows\win.ini` | `"path outside the data directory: C:\\Windows\\win.ini"` | false | không |
| `x\u0000y` | `"stat: embedded null character in path"` | false | không |

Payload của cả 5 chỉ có hai khoá `["found","error"]` — không có `summary`/`path`/`served_from`
(những trường chỉ xuất hiện khi đọc file thành công, `src/.../parse_ihex_summary.py:27`).

**Có file ngoài `data/` nào bị đọc không? KHÔNG.**
- 4/5 bị chặn trước khi mở file với thông điệp containment rõ ràng; `C:\Windows\win.ini` **có thật
  trên máy** (`Test-Path True`) nhưng response không chứa một byte nội dung nào — chỉ có lỗi.
- `A9_NULL`: chuỗi có byte null bị `stat`/pathlib ném `ValueError` trước khi đọc; đây là lỗi thô của
  Python chứ không phải thông điệp guard (khác 4 case kia), nhưng vẫn `found:false`, không đọc.
- Kiểm mã (chỉ đọc, không sửa): `tools/parse_ihex_summary.py:22` gọi `safe_data_path(path)` trước,
  `:25` mới `resolved.read_text(...)`; `paths.py:20` resolve, `:21–24` so containment với
  `data_root`/`data_root/local`, `:27` raise `UnsafePath` khi ngoài. Không có nhánh nào đọc file
  trước khi containment ⇒ 5 input này không thể đọc file ngoài `data/`.
Đúng kỳ vọng `:30` → PASS.

### 3.4 A10 — phần PASS

- **A10_RC_OPTIONS**: `@Bitmask` của `_OPTIONS` tại `libraries/RC_Channel/RC_Channels_VarInfo.h:96`
  (14 bit, từ `0:Ignore RC Receiver` … `13: Use 420kbaud for ELRS protocol`). Tự tính
  `0x2801 = 10241` → bits **[0, 11, 13]**, tên `[Ignore RC Receiver, Use Link Quality for RSSI with CRSF, Use 420kbaud for ELRS protocol]`.
  Tool khớp tuyệt đối (`raw/A10_RC_OPTIONS.json:29`):

```json
"found": true, "param": "_OPTIONS", "display_name": "RC options", "vehicle": "shared",
"version": "Copter-4.7.2", "mode": "decode", "value": 10241, "hex": "0x2801", "bin": "0b10100000000001",
"set_bits": [{"bit": 0, "name": "Ignore RC Receiver"},
             {"bit": 11, "name": "Use Link Quality for RSSI with CRSF"},
             {"bit": 13, "name": "Use 420kbaud for ELRS protocol"}],
"undefined_bits_set": []
```

  Cả 14 phần tử `bit_definitions` khớp từng tên với dòng nguồn 96 → PASS. (Tool trả `param:
  "_OPTIONS"` thay vì `"RC_OPTIONS"` — đó đúng là hậu tố `@Param` trong nguồn; không phải bịa.)
- **A10_LOG_BITMASK**: `@Bitmask` của LOG_BITMASK tại `ArduCopter/Parameters.cpp:210` (20 bit; bit
  14, 16 không định nghĩa). Tự tính `1025 = 0x401` → bits **[0, 10]**, tên `[Fast Attitude, RC output]`.
  Tool khớp (`raw/A10_LOG_BITMASK.json:29`):

```json
"found": true, "param": "LOG_BITMASK", "display_name": "Log bitmask", "vehicle": "ArduCopter",
"version": "Copter-4.7.2", "mode": "decode", "value": 1025, "hex": "0x401", "bin": "0b10000000001",
"set_bits": [{"bit": 0, "name": "Fast Attitude"}, {"bit": 10, "name": "RC output"}],
"undefined_bits_set": []
```

  20/20 `bit_definitions` khớp nguồn → PASS.
- **A10_BAD_BIT**: value `"This Bit Does Not Exist"` → `found:false`, `"error": "unknown bit name(s): ['this bit does not exist']"`,
  `known_bits` 14 tên đúng nguồn (`raw/A10_BAD_BIT.json:29`) → không bịa bit, PASS.
- **A10_NON_BITMASK**: `WPNAV_SPEED` → `found:false`, `"note": "parameter not found; nothing was invented"`.
  Hành vi đúng (không bịa), nhưng **đề không kiểm đúng nhánh dự định**: tại pin không còn
  `WPNAV_SPEED` — `libraries/AC_WPNav/AC_WPNav.cpp:141` và `:152` ghi
  `// old WPNAV_SPEED at index 0` với tên mới `"WP_SPD"`; mọi lần `WPNAV_SPEED` xuất hiện ở pin đều
  trong ReleaseNotes, không có `@Param`. Vì vậy đây là nhánh “không tìm thấy tham số”, không phải
  nhánh “tham số tồn tại nhưng không có `@Bitmask`” (nhánh đó, theo `decode_bitmask.py:46–49`, trả
  `note` khác). Chấm PASS cho hành vi nhưng nhánh cần kiểm chưa được kiểm — xem §7.

## 4. Bằng chứng thô

Quy ước: mỗi payload dưới đây là `response.content[0].text` của case tương ứng (đã giải mã lớp JSON);
toàn bộ payload nằm trên dòng raw đã dẫn. Với payload dài tôi trích đoạn — **giá trị giữ nguyên
văn**, chỉ gộp các dòng cho gọn và ghi rõ toàn văn ở dòng raw; chỗ lược bớt được đánh dấu `…`.

### 4.1 A1 — `raw/A1.json:27` (toàn bộ)

```json
{
  "found": false,
  "error": "odd number of hex digits"
}
```

input `raw/A1.json:6`: `"hex": "C81816E0031FF8C0073EF0810F7CE0031FF8C0073EF0810F7AD"` (51 ký tự);
`raw/A1.json:23`: `"isError": false`.

### 4.2 A2 — `raw/A2.json:27` (toàn bộ)

```json
{
  "found": false,
  "error": "odd number of hex digits"
}
```

input `raw/A2.json:6` (51 ký tự, kết thúc `…F7AC`); `raw/A2.json:23`: `"isError": false`.

### 4.3 A3 — `raw/A3.json:27` (trích nguyên văn; toàn văn tại dòng đó)

```json
"found": true, "byte_count": 26, "frame_count": 1, "all_crc_valid": true,
"frames": [{"offset": 0, "sync": 200, "length": 24, "type": 22,
  "type_name": "RC Channels Packed",
  "payload_hex": "ac001ff8c0073ef0810f7ce0031ff8c0073ef0816fe2",
  "crc": 140, "crc_computed": 140, "crc_valid": true,
  "channels": [{"channel": 1, "ticks": 172, "us": 987},
               {"channel": 2, "ticks": 992, "us": 1500}, … (kênh 3..15 y hệt kênh 2) …,
               {"channel": 16, "ticks": 1811, "us": 2011}]}],
"crc_polynomial": "0xD5, init 0, over Type+Payload (CRC over sync/length is wrong)",
```

`raw/A3.json:6` input; `raw/A3.json:23` `"isError": false`.

### 4.4 A4 — `raw/A4_*.json:27`

A4_XYZ (toàn bộ):

```json
{
  "found": false,
  "error": "no hex bytes supplied"
}
```

A4_ODD (toàn bộ):

```json
{
  "found": false,
  "error": "odd number of hex digits"
}
```

A4_EMPTY (toàn bộ):

```json
{
  "found": false,
  "error": "no hex bytes supplied"
}
```

A4_100K (`raw/A4_100K.json:27`, toàn bộ phần đầu; phần `citation` cũng có mặt):

```json
{
  "found": false,
  "byte_count": 50000,
  "frame_count": 0,
  "all_crc_valid": true,
  "frames": [],
  "crc_polynomial": "0xD5, init 0, over Type+Payload (CRC over sync/length is wrong)",
```

Input A4_100K `raw/A4_100K.json:6` dài đúng 100000 ký tự `A`; `duration_ms` = 15.7,
`transport_error` = null, `isError` = false (`raw/A4_100K.json:23`).

### 4.5 A5, A6, A7 — `raw/A5.json:27`, `raw/A6.json:27`, `raw/A7.json:27`

A5 (toàn bộ):

```json
{
  "found": true,
  "record_count": 1,
  "all_valid": true,
  "records": [{"line": ":10010000214601360121470136007EFE09D2190140", "valid": true,
               "byte_count": 16, "address": 256, "record_type": 0, "record_type_name": "data",
               "data_hex": "214601360121470136007efe09d21901",
               "checksum": 64, "checksum_expected": 64}]
}
```

A6 (toàn bộ):

```json
{
  "found": true,
  "record_count": 1,
  "all_valid": false,
  "records": [{"line": ":10010000214601360121470136007EFE09D2190141", "valid": false,
               "byte_count": 16, "address": 256, "record_type": 0, "record_type_name": "data",
               "data_hex": "214601360121470136007efe09d21901",
               "checksum": 65, "checksum_expected": 64, "error": "checksum mismatch"}]
}
```

A7 (toàn bộ):

```json
{
  "found": true,
  "record_count": 1,
  "all_valid": false,
  "records": [{"line": "10010000214601360121470136007EFE09D2190140", "valid": false,
               "error": "missing ':' start code"}]
}
```

Độc lập: A5 checksum 0x40 = 0x40 (hợp lệ); A6 0x41 ≠ 0x40; A7 không có start code. `isError`=false
(`raw/A5.json:23`, `raw/A6.json:23`, `raw/A7.json:23`).

### 4.6 A8 — `raw/A8_*.json:27`

Nguyên văn các trường nhận dạng trong payload từng file (cùng thứ tự khoá):

- HEARTBEAT: `"found": true, "query": "HEARTBEAT", "kind": "message", "resolved_by": "name", "msgid": 0, "name": "HEARTBEAT"`
- SYS_STATUS: `"found": true, …, "msgid": 1, "name": "SYS_STATUS"`
- ATTITUDE: `"found": true, …, "msgid": 30, "name": "ATTITUDE"`
- GLOBAL_POSITION_INT: `"found": true, …, "msgid": 33, "name": "GLOBAL_POSITION_INT"`
- RC_CHANNELS: `"found": true, …, "msgid": 65, "name": "RC_CHANNELS"`
- RC_CHANNELS_OVERRIDE: `"found": true, …, "msgid": 70, "name": "RC_CHANNELS_OVERRIDE"`
- COMMAND_LONG: `"found": true, …, "msgid": 76, "name": "COMMAND_LONG"`
- STATUSTEXT: `"found": true, …, "msgid": 253, "name": "STATUSTEXT"`

A8_NOT_A_MSG (`raw/A8_NOT_A_MSG.json:27`, toàn bộ):

```json
{
  "found": false,
  "query": "NOT_A_MSG",
  "candidates": ["HEARTBEAT","SYS_STATUS","SYSTEM_TIME","PING","CHANGE_OPERATOR_CONTROL",
    "CHANGE_OPERATOR_CONTROL_ACK","AUTH_KEY","LINK_NODE_STATUS","SET_MODE","PARAM_REQUEST_READ"],
  "note": "unknown MAVLink name; nothing was invented"
}
```

Mỗi payload A8 kèm citation `"ref": "eec8824212c1fe8c5d8f5181fcfdef54ee219b63"` với
`"path"` lần lượt `minimal.xml` / `common.xml` / `standard.xml` và `"lines"` đã ghi ở §3.2.

### 4.7 A9 — `raw/A9_*.json:27` (toàn bộ từng payload)

```json
// A9_TRAV_UNIX
{"found": false, "error": "path outside the data directory: ../../etc/passwd"}
// A9_TRAV_WIN
{"found": false, "error": "path outside the data directory: ..\\..\\Windows\\win.ini"}
// A9_ABS_UNIX
{"found": false, "error": "path outside the data directory: /etc/passwd"}
// A9_ABS_WIN
{"found": false, "error": "path outside the data directory: C:\\Windows\\win.ini"}
// A9_NULL
{"found": false, "error": "stat: embedded null character in path"}
```

(Chuỗi lỗi trong file JSON có escape `\\`; payload giải mã giữ nguyên backslash như trên.)
`isError` của cả 5 = false (`raw/A9_*.json:23`).

### 4.8 A10 — `raw/A10_*.json:29`

A10_RC_OPTIONS (trích nguyên văn các trường quyết định; `bit_definitions` 14 phần tử khớp nguồn):

```json
{
  "found": true, "param": "_OPTIONS", "display_name": "RC options", "vehicle": "shared",
  "version": "Copter-4.7.2", "mode": "decode", "value": 10241,
  "hex": "0x2801", "bin": "0b10100000000001",
  "set_bits": [{"bit": 0, "name": "Ignore RC Receiver"},
               {"bit": 11, "name": "Use Link Quality for RSSI with CRSF"},
               {"bit": 13, "name": "Use 420kbaud for ELRS protocol"}],
  "undefined_bits_set": []
}
```

A10_LOG_BITMASK (trích nguyên văn):

```json
{
  "found": true, "param": "LOG_BITMASK", "display_name": "Log bitmask", "vehicle": "ArduCopter",
  "version": "Copter-4.7.2", "mode": "decode", "value": 1025,
  "hex": "0x401", "bin": "0b10000000001",
  "set_bits": [{"bit": 0, "name": "Fast Attitude"}, {"bit": 10, "name": "RC output"}],
  "undefined_bits_set": []
}
```

A10_ARMING_CHECK (toàn bộ):

```json
{
  "found": false,
  "param": "ARMING_CHECK",
  "candidates": ["_XY_IMAX","_FLOW_MAX","_FILT_HZ","_QUAL_MIN","_BRAKE_RATE","SPD_MS","SPD_HIGH_MS","ALT_LOW_M"],
  "note": "parameter not found; nothing was invented"
}
```

A10_NON_BITMASK (toàn bộ):

```json
{
  "found": false,
  "param": "WPNAV_SPEED",
  "candidates": ["_XY_IMAX","_FLOW_MAX","_FILT_HZ","_QUAL_MIN","_BRAKE_RATE","SPD_MS","SPD_HIGH_MS","ALT_LOW_M"],
  "note": "parameter not found; nothing was invented"
}
```

A10_BAD_BIT (toàn bộ; `known_bits` 14 tên nêu đủ ở payload):

```json
{
  "found": false,
  "param": "_OPTIONS",
  "error": "unknown bit name(s): ['this bit does not exist']",
  "known_bits": ["Ignore RC Receiver", "Ignore MAVLink Overrides",
    "Ignore Receiver Failsafe bit but allow other RC failsafes if setup", "FPort Pad",
    "Log RC input bytes", "Arming check throttle for 0 input",
    "Skip the arming check for neutral Roll/Pitch/Yaw sticks", "Allow Switch reverse",
    "Use passthrough for CRSF telemetry", "Suppress CRSF mode/rate message for ELRS systems",
    "Enable multiple receiver support", "Use Link Quality for RSSI with CRSF",
    "Annotate CRSF flight mode with * on disarm", "Use 420kbaud for ELRS protocol"]
}
```

`isError` của cả 5 = false (`raw/A10_*.json:25`).

## 5. Hai rerun công bố (báo riêng, không dùng để biến A1/A2 thành PASS)

`raw/A1_RERUN_CORRECTED.json:1–7`: `"note": "DISCLOSED RERUN: A1 with the missing nibble restored
(52 chars)"`, input `…F0810F7CAD`. Payload (`:27`): `"found": true, "byte_count": 26,
"frame_count": 1, "all_crc_valid": true`, frame `"crc": 173, "crc_computed": 173, "crc_valid": true`,
`"payload_hex": "e0031ff8c0073ef0810f7ce0031ff8c0073ef0810f7c"`, 16 kênh đều
`{"channel": N, "ticks": 992, "us": 1500}` — khớp đầy đủ kỳ vọng A1.

`raw/A2_RERUN_CORRECTED.json:1–7`: `"note": "DISCLOSED RERUN: A2 with the missing nibble restored
(valid frame, bad CRC)"`, input `…F0810F7CAC`. Payload (`:27`): `"found": true,
"all_crc_valid": false`, frame `"crc": 172, "crc_computed": 173, "crc_valid": false` — khớp kỳ
vọng A2 (báo CRC sai). Frame vẫn được liệt kê với 16 kênh `ticks: 992`; tool không đánh dấu hợp lệ.

Hai rerun này chỉ dùng để xác nhận chẩn đoán lỗi input ở §2.1–2.2; chúng **không** thay đổi verdict
FAIL của A1/A2.

## 6. Chỗ tool trả điều nguồn ghim không ủng hộ

### 6.1 µs của CRSF lệch 1 ở kênh dưới tâm (A3)

Tool trả `"channel": 1, "ticks": 172, "us": 987` (`raw/A3.json:27`). Công thức nguồn ghim
`crsf_spec:crsf.md:526`: `#define TICKS_TO_US(x) ((x - 992) * 5 / 8 + 1500)` với phép chia nguyên
C (truncate về 0): `(172-992)*5 = -4100`, `-4100/8 = -512`, `+1500 = 988`. Tool cho 987 ⇒ lệch −1
µs ở phía dưới 992 (kênh 16: 2011 = 2011, khớp vì phép chia dương). Kỳ vọng A3 không ràng `us`
nên A3 vẫn PASS, nhưng giá trị `us` của tool không khớp định nghĩa nguồn. (Nghi vấn: tool chia
kiểu floor ở bước `(x-992)*5/8` rồi mới cộng 1500.)

### 6.2 `found:false` không kèm lý do rõ cho 100000 ký tự hex (A4_100K)

`raw/A4_100K.json:27` có `"found": false` nhưng **không** có `"error"`/`"note"`; lý do chỉ suy ra từ
`"frame_count": 0, "frames": []`. Ba case A4 còn lại đều có chuỗi lỗi rõ. Thêm nữa
`"all_crc_valid": true` khi không có frame nào là đúng rỗng (vacuous) nhưng dễ bị đọc thành “CRC
hợp lệ”. Đề `:25` cho phép “isError hoặc found:false có lý do”, nên tôi chấm PASS ở mức tối thiểu,
nhưng đây là điểm thiếu nếu hiểu “lỗi rõ ràng” là phải có chuỗi lỗi.

### 6.3 Gợi ý thay thế của A10 vô dụng

Với ARMING_CHECK (đã bị đổi tên ở pin), `candidates` là 8 param đầu tiên của bảng
(`_XY_IMAX`, `_FLOW_MAX`, …), không hề gợi ý `ARMING_SKIPCHK`/`SKIPCHK`
(`raw/A10_ARMING_CHECK.json:29`). Không trái nguồn (danh sách này không phải khẳng định về nguồn)
nhưng là chất lượng gợi ý kém, cùng danh sách y hệt xuất hiện cho WPNAV_SPEED.

### 6.4 Ghi chú citation HEARTBEAT (ngoài phạm vi A8, chuyển mục G)

Với HEARTBEAT, tool trích `minimal.xml#L730-L757` (`raw/A8_HEARTBEAT.json:27`) trong khi
`<message id="0" name="HEARTBEAT">` ở dòng 747; `excerpt` của citation là các `<entry>` enum
MAV_COMP_ID (bắt đầu dòng 730), không chứa dòng định nghĩa message. msgid vẫn đúng (dòng 747) nên
A8 PASS, nhưng citation không trỏ đúng thân message — cần mục G xem xét.

## 7. Những gì không kiểm được / giới hạn

1. **A1/A2:** không thể tính CRC/ticks từ chính input đóng băng (51 ký tự) — chỉ tính được từ dạng
   52 ký tự suy ra bằng cách chèn `C` tại index 49 (khớp rerun công bố). Việc “input đúng ý tác giả”
   là suy luận từ kỳ vọng + rerun, không chứng minh được từ file đóng băng.
2. **A10_ARMING_CHECK:** không tồn tại `@Bitmask` của ARMING_CHECK tại pin nên không thể đối chiếu
   bit set như đề yêu cầu; chỉ đối chiếu được tham số kế nhiệm ARMING_SKIPCHK
   (`AP_Arming.cpp:198`) và kết luận `found:false` là đúng. Kiểm phụ trên index
   (`data/index.sqlite`, bảng `params`): chỉ có `name_raw = "SKIPCHK"`, không có
   `"ARMING_SKIPCHK"`; nếu gọi đúng tên mới thì hiện cũng chưa decode được — vấn đề đặt tên/đầy
   đủ của index thuộc phạm vi B, tôi không kết luận ở đây.
3. **A10_NON_BITMASK:** nhánh “tham số tồn tại nhưng không có `@Bitmask`” chưa được kiểm vì
   `WPNAV_SPEED` không tồn tại tại pin (đổi tên thành `WP_SPD`, `AC_WPNav.cpp:141/152`). Chỉ kiểm
   được nhánh “không tìm thấy tham số”.
4. **A4_100K:** “trả lỗi rõ ràng” — tool không có chuỗi lỗi (xem §6.2); tôi chấm PASS theo
   “found:false có lý do”, không phải theo “có trường error”.
5. **A9:** hộp đen chỉ chứng minh response không chứa nội dung file (và kiểm mã cho thấy
   `read_text` chỉ chạy sau containment); không thể chứng minh tuyệt đối bằng quan sát rằng tool
   “không hề mở” file. Lưu ý `/etc/passwd` không tồn tại trên Windows nên case đó không thể “đọc
   thành công” dù guard hỏng; `C:\Windows\win.ini` tồn tại thật (Test-Path True) nên case
   `A9_ABS_WIN` mới có ý nghĩa.
6. **A8:** chỉ đối chiếu msgid + sự tồn tại/không tồn tại của tên; nội dung `description`/`fields`
   của 8 message không thuộc kỳ vọng A8 nên không kiểm từng field.
7. Không kiểm lại tính đúng của chính `scripts/blackbox_independent.py` ngoài việc đối chiếu chéo
   với nguồn ghim (`crsf.md`, XML mavlink, `@Bitmask`) — mọi kết quả trong báo cáo đều khớp cả hai
   phía.

## 8. Kết luận mục A

- 14/17 dòng PASS. 3 FAIL: A1, A2 (cùng một lỗi: chuỗi hex đóng băng thiếu nibble `C` ở index 49)
  và A10_ARMING_CHECK (tham số không tồn tại tại tag Copter-4.7.2 — đã đổi tên thành
  ARMING_SKIPCHK). Cả 3 đều là **KỲ VỌNG CỦA TÔI SAI**, không có case nào kết luận TOOL SAI.
- Không có case nào “KHÔNG XÁC ĐỊNH”.
- Điểm cần sửa ngoài kỳ vọng: µs CRSF lệch 1 ở nửa dưới tâm (§6.1); thiếu lý do lỗi cho input
  100000 ký tự (§6.2); candidates vô dụng (§6.3); citation HEARTBEAT chưa trỏ thân message (§6.4,
  chuyển G).
