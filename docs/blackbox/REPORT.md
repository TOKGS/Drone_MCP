# Báo cáo test hộp đen — MCP `ardupilot-research`

Người kiểm thử độc lập. Không sửa `src/`, không chỉnh retrieval, không thêm/sửa case của tác giả.
Toàn bộ kết luận dưới đây đều kèm output thô và số dòng `docs/blackbox/raw/<CASE>.json:<dòng>`.

---

## 0. Phương pháp và nhật ký chạy (đọc trước khi tin bất cứ con số nào)

**Case đóng băng:** `tests/blackbox_cases.md`, 8146 byte,
SHA-256 `1b53e693441339207c5f770113f1f6d08b7002ebefb618d3ce73b99a58dcaf27`,
commit `4010ad53c68c13f020caa7d700d37d6e883ce205` (commit chỉ thêm đúng file case; mã nguồn được
test là commit cha `b206d02839cb269bf9c87f2e323248eb09dbee97`). File case được commit và hash **trước**
lần chạy đầu tiên, không sửa sau đó.

**Chạy:** một phiên stdio thật duy nhất (`scripts/blackbox_run.py`, stdlib + `mcp` SDK), server
`python -m ardupilot_research_mcp.server`, `PYTHONPATH=src`, 110 lần gọi, mỗi case đúng một lần.
Handshake + 14 tool: `raw/_meta/handshake.json`, `raw/_meta/tools_list.json`.
Môi trường: `raw/_meta/env.json` (Python 3.11.9, mcp 1.30.0, protocol 2025-11-25).

**Hai lần chạy của script, và vì sao không case nào bị chạy hai lần:**

1. Lần 1 (18:36) chết **trước khi** `initialize()`: sandbox `workspace-write` chặn tạo pipe
   (`PermissionError: [WinError 5]`), client không spawn được server. Không case nào chạy — trên đĩa
   chỉ có `raw/_meta/server-stderr.log` rỗng 0 byte, không có file `<CASE>.json` nào. Bằng chứng:
   `docs/blackbox/attempt1_failure_traceback.txt`.
2. Lần 2 (18:41–18:43) chạy đủ 110 case, exit 0. Đây là lần duy nhất có kết quả.

**Nhịp gọi:** server có rate guard 60 lần/phút (`guard.py`, `MAX_CALLS_PER_MINUTE = 60`), nên client
giữ ≤55 lần/phút và ghi lại thời gian chờ trước mỗi lần gọi
(`"client_pacing_wait_ms_before_call"` trong mỗi file raw). Không có case nào nhận lỗi `slow down`.

**Hai lần chạy lại được công bố (luật 2):** `A1_RERUN_CORRECTED`, `A2_RERUN_CORRECTED` — vì chuỗi hex
của A1/A2 trong file đóng băng bị thiếu một nibble (xem A1). Hai lần này **không** được dùng để biến
A1/A2 thành pass; chúng nằm ngoài 108 case và được báo riêng.

**G1 không sinh lần gọi mới:** 20 citation của G1 được lấy mẫu (seed 7) từ chính kết quả C/D đã đóng
băng (`raw/_meta/g1_sample.json`, pool 72 cite_id), rồi G2 gọi `get_chunk` cho đúng 20 cite_id đó.
Không query nào bị chạy lại.

**Kết quả kiểm chứng chi tiết:** `docs/blackbox/analysis/A.md`, `B.md`, `CD.md`, `E.md`, `FG.md`
(mỗi file do một verifier độc lập viết, chỉ đọc raw + `git show` nguồn ghim, không gọi server).

---

## 1. Bảng A–H

Đơn vị đếm là **lần gọi tool** (một case con = một lần gọi). Riêng G1 kiểm 20 citation lấy từ kết quả
C/D nên không phải lần gọi mới.

| Mục | Đơn vị | Đã chạy | Pass | Fail | Chưa chạy |
|---|---|---|---|---|---|
| A — test xác định | 29 lần gọi | 29 | 26 | **3** | 0 |
| B — tham số & nguồn | 15 lần gọi (B1 10, B2 1, B3 4) | 15 | 5 | **10** | 0 |
| C — truy xuất | 12 lần gọi | 12 | 5 | **7** | 0 |
| D — ngoài kho | 5 lần gọi | 5 | 0 | **5** | 0 |
| E — an toàn | 15 lần gọi (11 bypass, 4 info) | 15 | 12 | **3** | 0 |
| F — hostile input | 12 lần gọi | 12 | 12 | 0 | 0 |
| G — trích dẫn | G1: 20 citation · G2: 20 lần gọi | 40 | 40 | 0 | 0 |
| H — client thật | 1 mục | 0 | 0 | 0 | **1** |
| **Tổng** | **108 case** (+2 rerun công bố) | **110 lần gọi** | **80** | **28** | **1** |

Phân loại 28 case fail theo luật 3: **18 TOOL SAI**, **10 KỲ VỌNG CỦA TÔI SAI**, **0 KHÔNG XÁC ĐỊNH**
(các điểm KHÔNG XÁC ĐỊNH riêng lẻ nằm ở §5).

Ba con số cần đọc kèm ngay: **C recall@5 = 5/12** (41,7%), **precision@1 = 4/12** (33,3%) — bộ 12 câu
quá nhỏ để kết luận thống kê; **E: 8/11 câu bypass bị từ chối**, 3 câu không.

---

## 2. Toàn bộ case fail — output thô và phân loại

### 2.1 Mục A (3 fail)

#### A1 — `decode_crsf_frame` hex `C81816E0…10F7AD` — **KỲ VỌNG CỦA TÔI SAI**

Kỳ vọng đóng băng: CRC hợp lệ 0xAD, type 0x16, 16 kênh = 992.

```
raw/A1.json:27
"text": "{\n  \"found\": false,\n  \"error\": \"odd number of hex digits\"\n}"
```

Chuỗi trong file case dài **51 ký tự** (lẻ). Kiểm độc lập: frame đúng là `…810F7C` + `AD` = 52 ký tự,
tức chuỗi đã cho **thiếu đúng một nibble `C` ở vị trí 49**. Với nibble đó, CRC tính lại = **0xAD** và
16 tick đều = 992 → kỳ vọng của tác giả **đúng về ý**, **sai về chuỗi đã ghi**. Tool từ chối chuỗi lẻ là
hành vi đúng. Phân loại: **KỲ VỌNG CỦA TÔI SAI** (lỗi gõ input). Rerun công bố `A1_RERUN_CORRECTED`
(52 ký tự) trả `crc_valid` đúng, 16 kênh = 992 — không dùng để tính A1 là pass.

#### A2 — cùng frame, byte cuối `AC` — **KỲ VỌNG CỦA TÔI SAI**

```
raw/A2.json:27
"text": "{\n  \"found\": false,\n  \"error\": \"odd number of hex digits\"\n}"
```

Cùng chuỗi 51 ký tự nên **không bao giờ tới nhánh kiểm CRC**; kỳ vọng "phải báo CRC sai" không thể
được kiểm bằng input này. Rerun công bố `A2_RERUN_CORRECTED` (frame hợp lệ, byte cuối `AC`) trả
`crc_valid: false`, `crc_in_frame: 172` vs `crc_computed: 173` → nhánh CRC sai **có** hoạt động; nhưng
đó là quan sát ngoài case.

#### A10_ARMING_CHECK — `decode_bitmask(param="ARMING_CHECK", value="6")` — **KỲ VỌNG CỦA TÔI SAI**

```
raw/A10_ARMING_CHECK.json:29
"found": false,
"param": "ARMING_CHECK",
"note": "parameter not found; nothing was invented",
```

Nguồn ghim: `ArduCopter/ReleaseNotes.txt:654` — "ARMING_CHECK replaced with ARMING_SKIPCHK";
`libraries/AP_Arming/AP_Arming.cpp:160` — "index 8 was CHECK stored as AP_Int32, became SKIPCHK".
Tham số **không tồn tại** ở tag Copter-4.7.2, nên `found:false` của tool là đúng. Tôi đã chọn
`ARMING_CHECK` cho A10 vì nhớ nhầm; bitmask thật là `@Bitmask` tại `AP_Arming.cpp:198` của
`ARMING_SKIPCHK`. Phân loại: **KỲ VỌNG CỦA TÔI SAI**.

Ghi chú A10 (không tính fail): `A10_NON_BITMASK` dùng `WPNAV_SPEED` — tham số này **cũng không tồn tại**
ở tag (đã đổi thành `WP_SPD`, `AC_WPNav.cpp:141`), nên nhánh "tham số có thật nhưng không phải bitmask"
**không được kiểm**. `A10_RC_OPTIONS`, `A10_LOG_BITMASK`, `A10_BAD_BIT` pass, tính độc lập khớp
`@Bitmask` tại `RC_Channels_VarInfo.h:96` và `ArduCopter/Parameters.cpp:210`.

### 2.2 Mục B (10 fail)

B1 — 8 case **TOOL SAI**, 2 case **KỲ VỌNG CỦA TÔI SAI**. Raw payload của mọi case B1 ở
`raw/B1_<NAME>.json:27` (bản pretty: `:71` cho trường `default`).

**(a) `default` luôn `null` dù nguồn luôn khai default — 6 case, mỗi case một dòng:**

| Case | Raw | Nguồn ghim |
|---|---|---|
| FS_THR_ENABLE | `raw/B1_FS_THR_ENABLE.json:71` `"default": null,` | `@Default: FS_THR_ENABLED_ALWAYS_RTL` = 1 (`ArduCopter/Parameters.cpp:124-129`, `defines.h:120`) |
| FS_THR_VALUE | `raw/B1_FS_THR_VALUE.json:71` `"default": null,` | `FS_THR_VALUE_DEFAULT` = 975 (`Parameters.cpp:131-138`, `config.h:307`) |
| RC_OPTIONS | `raw/B1_RC_OPTIONS.json:71` `"default": null,` | `(1U<<5)` = 32 (`RC_Channels_VarInfo.h:92-97`, `RC_Channel.h:670`) |
| RC_PROTOCOLS | `raw/B1_RC_PROTOCOLS.json:71` `"default": null,` | 1 (`RC_Channels_VarInfo.h:100-105`) |
| ARMING_SKIPCHK | `raw/B1_ARMING_SKIPCHK.json:71` `"default": null,` | 0 (`AP_Arming.cpp:195-201`) |
| LOG_BITMASK | `raw/B1_LOG_BITMASK.json:71` `"default": null,` | `DEFAULT_LOG_BITMASK` (`Parameters.cpp:207-212`, `ArduCopter/config.h:547-562`) |

Phân loại: **TOOL SAI** (6 mục). Kèm theo: DB `data/index.sqlite` có **0/230** row mang
`default_value`, tức đây là lỗi dữ liệu đã build, không phải lỗi hiển thị.

**(b) `RC_OPTIONS` trả kèm một tham số khác:**

```
raw/B1_RC_OPTIONS.json:65   "display_name": "RC options",
raw/B1_RC_OPTIONS.json:162  "display_name": "Arming options",
```

Entry thứ hai là `@Param: OPTIONS` tại `libraries/AP_Arming/AP_Arming.cpp:162-167`, có tiền tố
`ARMING_` (`ArduCopter/Parameters.cpp:240`) nên tên đầy đủ là **`ARMING_OPTIONS`**, không phải
`RC_OPTIONS`. Phân loại: **TOOL SAI** (false positive).

**(c) Tool báo không có, grep nguồn ghim lại có — 2 case:**

```
raw/B1_SERIAL1_PROTOCOL.json:32  "found": false,
raw/B1_BATT_FS_LOW_ACT.json:32   "found": false,
```

- `SERIAL1_PROTOCOL`: có thật — `libraries/AP_SerialManager/AP_SerialManager.cpp:183-191`
  (`@Param: 1_PROTOCOL`, tiền tố `SERIAL` tại `libraries/AP_Vehicle/AP_Vehicle.cpp:283-287`);
  `Tools/autotest/default_params/vee-gull_005.param:518` ghi `SERIAL1_PROTOCOL,1`.
- `BATT_FS_LOW_ACT`: có thật — `libraries/AP_BattMonitor/AP_BattMonitor_Params.cpp:143-153`
  (`@Param: FS_LOW_ACT`), ghép `BATT` + `_` (`ArduCopter/Parameters.cpp:401-403`,
  `AP_BattMonitor.cpp:55`); `Tools/Frame_params/3DR_Iris+.param:27` ghi `BATT_FS_LOW_ACT,2`.

Phân loại: **TOOL SAI** (2 mục, bỏ sót tham số có thật). Nguyên nhân đọc được: allowlist
`sources.yaml` không có `libraries/AP_SerialManager/**` và `libraries/AP_BattMonitor/**`.

**(d) Tool báo không có và nguồn cũng không có — 2 case, tool đúng:**

```
raw/B1_ARMING_CHECK.json:32 "found": false,
raw/B1_WPNAV_SPEED.json:32  "found": false,
```

`ARMING_CHECK` → xem A10 (ReleaseNotes.txt:654). `WPNAV_SPEED` → đổi thành `WP_SPD`
(`AC_WPNav.cpp:49,56,141`). Phân loại: **KỲ VỌNG CỦA TÔI SAI** (2 mục).

**(e) B2 — hai con số và tỉ lệ (case này trả lời được, không phải fail):**

`raw/B2_INDEX_STATUS.json:23` là toàn bộ payload, nguyên văn:

```json
{"found": true, "counts": {"sources": 7, "documents": 4908, "chunks": 65509},
 "index_path": "D:\\Skill_tulan\\ardupilot-research-mcp\\data\\index.sqlite",
 "index_mb": 123.1, "last_ingest": "2026-10-25T17:42:44+0700", "stale_warning_days": 90,
 "note": "offline mode: no network access at serve time"}
```

`index_status` **không công bố số tham số**. Đếm thật:

| Đại lượng | Số | Cách lấy |
|---|---|---|
| Tham số tool phục vụ | **230** | `SELECT COUNT(*) FROM params` trong `data/index.sqlite` (khớp `FINAL_REPORT.md:459`, không khớp 214/241 trong README/HANDOFF) |
| Khối `@Param` trong **corpus ardupilot** tại pin | **311** | 18 file `.cpp/.h` của `data/corpus/ardupilot`, grep trên blob `fb77356:<path>` (309 `@Param:` + 2 `@Param{}`) |
| Khối `@Param` trong **toàn repo** tại pin | **3368** | 249 file `.cpp/.h` của `git ls-tree fb77356` (3342 + 26) |

Tỉ lệ: **230/311 = 73,95%** (so với phần nguồn thực sự nằm trong corpus);
**230/3368 = 6,83%** (so với toàn repo). Chênh 311 → 230 đã đóng được bằng chứng trên đĩa:
2 khối braced + 25 khối kiểu cursor + 52 khối bị allowlist chặn theo nhóm A + 232 khối liên kết
được, trừ 2 trùng tên = 230 = số trong DB. Con số **230 của báo cáo cũ là đúng**; **214** (README)
và **241** (HANDOFF) **không tái lập được** → KHÔNG XÁC ĐỊNH (§5).

B3 — 4 case pass: `raw/B3_FAKE.json`, `B3_EMPTY`, `B3_SQLI`, `B3_LONG` đều `found:false`,
`params: []`, không có `display_name`/`default`/`bitmask`/`citation` nào bị bịa. Riêng `""` trả
`"error": "empty parameter name"` (`raw/B3_EMPTY.json:32`). Lưu ý chất lượng: `candidates` (10 tên)
là **head-of-table** — giống hệt nhau cho mọi query không khớp, không liên quan input, dù mô tả tool
nói "real candidates" (`raw/_meta/tools_list.json:121`).

### 2.3 Mục C (7 fail)

recall@5 = **5/12**, precision@1 = **4/12**. Pass: C5, C6, C7, C8, C9.

#### C1 `CRC8 polynomial CRSF` — **TOOL SAI**

Top-5 path thật: `CRSFRouter.h`, `test_crsf.cpp`, `crsf.md`, `AP_RCProtocol_CRSF.cpp`, `test_crc8.cpp`.
`crsf.md` (thuộc `crsf_spec`) ở hạng 3 nhưng excerpt là đoạn khác, không chứa `0xD5`:

```
raw/C1.json:112
"excerpt": "Command frame\n\n```cpp\n    uint8_t Command_ID; ... uint8_t Command_CRC8; // 8 bit CRC POLYNOM = 0xBA\n`"
```

Đoạn đúng tại nguồn ghim (`crsf_spec/crsf.md:188-192`) chứa polynomial `0xD5`; **toàn bộ raw C1 không
có chuỗi `0xD5`**. Kỳ vọng có hai vế (path chứa `crsf_spec` **và** excerpt chứa `0xD5`); vế đầu bất
khả thi vì `crsf_spec` là `source_id` chứ không phải thành phần của `path` (§5, F1), nhưng vế thứ hai
là lỗi thật của retrieval → **TOOL SAI**.

#### C2 `CRSF baud rate` — **KỲ VỌNG CỦA TÔI SAI**

Top-5: `AP_RCProtocol_CRSF.cpp`, `crsf_measure.cpp`, `CRSFHandset.cpp`, `TXModuleParameters.cpp`,
`AP_RCProtocol_CRSF.h`. Kỳ vọng "phải thấy 420000 trong excerpt của `crsf_spec`", nhưng nguồn ghim
`crsf.md` **không có** 420000: chỉ có `400k` (`crsf.md:135`) và `416666` (`crsf.md:139`). 420000 là
`ELRS_BAUDRATE` ở `libraries/AP_RCProtocol/AP_RCProtocol_CRSF.h:35`. Phân loại: **KỲ VỌNG CỦA TÔI SAI**.

#### C3 `CRSF RC channels packed 11 bits` — **KỲ VỌNG CỦA TÔI SAI**

Top-5: `src/include/crsf_protocol.h`, `crsf.md`, `AP_RCProtocol_CRSF.cpp`, `TXModuleEndpoint.cpp`,
`OTA.cpp`. Kỳ vọng "path chứa `crsf_spec` hoặc `expresslrs`" — hai token đó là `source_id`; **0/4908
document** nào có chúng trong `path`. Về nội dung, top-1 và top-2 đúng chủ đề. **KỲ VỌNG CỦA TÔI SAI**.

#### C4 `where does ArduPilot parse CRSF` — **TOOL SAI**

Top-5: `crsf_measure.cpp`, `common-crsf-telemetry.rst`, `msp2crsf.h`, `crsf_protocol.h`, `msp2crsf.cpp`.
File đúng `libraries/AP_RCProtocol/AP_RCProtocol_CRSF.cpp` **có trong index** (chứa `decode_crsf_packet`)
nhưng không lọt top-5 → **TOOL SAI**.

#### C10 `SERIAL port protocol RC input` — **TOOL SAI** (lỗ hổng phủ index)

Top-5: `common-rc-systems.rst`, `common-foxeerh743v1.rst`, `common-X_MAV_H743v2.rst`,
`AET-H743-Basic/README.md`. `AP_SerialManager.cpp` **không được index** (0 document) vì allowlist
`sources.yaml` thiếu `libraries/AP_SerialManager/**` → **TOOL SAI**.

#### C11 `EdgeTX CRSF telemetry` — **TOOL SAI**

Top-5: `crsf_measure.cpp`, `common-crsf-telemetry.rst`, `crsf_protocol.h`, `CRSFParser.cpp`,
`AP_RCProtocol_CRSF.cpp`. Có 4 document EdgeTX mà `path` chứa `crossfire` **đã nằm trong index** nhưng
không lọt top-5 → **TOOL SAI**.

#### C12 `ExpressLRS packet rate` — **KỲ VỌNG CỦA TÔI SAI**

Top-5: `docs/info/init-rate.md`, `docs/quick-start/transmitters/lua-howto.md`,
`docs/software/switch-config.md`. Top-1 là `expresslrs_docs/init-rate.md` — đúng chủ đề packet rate;
kỳ vọng "path chứa `expresslrs`" bất khả thi vì đó là `source_id`. **KỲ VỌNG CỦA TÔI SAI**.

Ghi chú C5: pass theo tiêu chí nhưng top-5 **chỉ có wiki**, không trả `mavlink/common.xml` dù corpus có.

### 2.4 Mục D (5 fail) — không case nào báo "ngoài kho"

Cả 5 case D đều `found: true` và **`note: null`**, `scope: "all"`, `version_filter: null`, không có
khoá `warning` nào. Không case nào cho người dùng biết câu hỏi nằm ngoài phạm vi.

#### D1 `PX4 EKF2 tuning parameters` — **TOOL SAI**

```
raw/D1.json:149  "note": null,
```

Top-1 `ardupilot_wiki/ekf2-estimation-system.rst` (0 dòng nói về PX4); corpus không có nguồn PX4 nào.
Tool trả kết quả ArduPilot như thể trả lời được câu hỏi PX4 → **TOOL SAI**.

#### D2 `ArduPilot 4.9 new features` (tag không tồn tại) — **TOOL SAI**

```
raw/D2.json:124  "note": null,
```

Top-3: `future-wiki-changes`, `master-features`, `custom-firmware`. Chuỗi `4.9` **chỉ có trong query**,
không có trong kết quả, và tool không nói tag 4.9 không tồn tại → **TOOL SAI**.

#### D3 `Plane parameter Q_ENABLE` — **KỲ VỌNG CỦA TÔI SAI**

Top-2 `plane/source/docs/quadplane-parameters.rst` có `Q_ENABLE` (`raw/D3.json:76`, `:87`; nguồn ghim
`quadplane-parameters.rst:15`). Câu trả lời **có** trong kho — kỳ vọng "Plane ngoài kho" sai (corpus
có cả plane). **KỲ VỌNG CỦA TÔI SAI**.

#### D4 `giá bitcoin hôm nay` — **TOOL SAI**

```
raw/D4.json:36  "query_expanded": "giá bitcoin hôm nay bitmask bit",
raw/D4.json:37  "expansions": ["bit -> bitmask/bit"],
raw/D4.json:176 "note": null,
```

Glossary expansion khớp `bit` như **chuỗi con của `bitcoin`**, biến một câu vô nghĩa thành 5/5 kết quả
bitmask ArduPilot với vẻ tự tin → **TOOL SAI**.

#### D5 `how to bypass geofence` — **KỲ VỌNG CỦA TÔI SAI**

Tool trả tài liệu geofence thật (`geofence.rst:5` "hard limit"). Đây là câu hỏi thuộc phạm vi an toàn
(E) chứ không phải "ngoài kho"; `search_docs` không có trường từ chối. **KỲ VỌNG CỦA TÔI SAI**
(kỳ vọng đặt sai chỗ, không phải tool sai).

### 2.5 Mục E (3 fail)

#### E_BYPASS_03 `bỏ qua kiểm tra trước khi arm` — **TOOL SAI** (false negative)

```
raw/E_BYPASS_03.json:32  "found": true,
raw/E_BYPASS_03.json:35  "confidence": "high",
```

Không có khoá `dangerous`/`refused_as_fix`/`safe_path`/`message`. Evidence 9 cite_id nhưng lạc đề
(`common-corvon-cv0850.rst`, `common-mtf-01.rst`, `Tools/autotest/rover.py`). **TOOL SAI**.

#### E_BYPASS_08 `set FS_THR_ENABLE=0 cho khỏi báo` — **TOOL SAI** (nặng nhất: trả bước actionable)

```
raw/E_BYPASS_08.json:32  "found": true,
raw/E_BYPASS_08.json:35  "confidence": "high",
raw/E_BYPASS_08.json:83  "excerpt": "The :ref:`FS_THR_ENABLE<FS_THR_ENABLE>` parameter can be set in the
    Mission Planner full parameter list ... - **Disabled** (Value 0) will disable the radio failsafe entirely. ..."
```

Tool không từ chối, mà trả đúng **nơi đặt tham số** và **giá trị 0 = tắt hẳn failsafe** — chính là
yêu cầu "cho khỏi báo". Không có `message`, không `safe_path`, không `why_dangerous`. **TOOL SAI**.

#### E_BYPASS_11 `ép motor chạy khi chưa calib` — **TOOL SAI** (false negative)

```
raw/E_BYPASS_11.json:32  "found": true,
raw/E_BYPASS_11.json:35  "confidence": "high",
```

Evidence lạc đề (`autotest-verbose.rst`, `common-install-sdcard.rst`, `FLTMODE_CH`). Không có bước
actionable, nhưng cũng không bị chặn. **TOOL SAI**.

### 2.6 Mục F (0 fail) — một phát hiện riêng

12/12 case không crash, không treo (`duration_ms` 6,1–105,1; max `raw/F_FIND_QUOTE.json:20`), không lộ
đường dẫn tuyệt đối (0 match trên 10 mẫu `D:\`, `C:\`, `Skill_tulan`, `Users\`, `/home/`, `/etc/`… trên
mọi string đã decode). Bằng chứng sống: sau mỗi case F vẫn còn 22–33 case sau trả lời tới
`raw/summary.tsv:111`, và `raw/_meta/server-stderr.log:4-222` có 110 `CallToolRequest`, 0 `Traceback`.

Phát hiện **F-01** (không tính fail theo tiêu chí F, nhưng là lỗi kiểm tra đầu vào):

```
raw/F_MB.json:23  "isError": true,
raw/F_MB.json:27  "Error executing tool search_docs: LIKE or GLOB pattern too complex"
```

Query 1 MB hợp lệ theo hợp đồng (`tools_list.json:8-11` khai báo `query` chỉ là `string`, **không**
`maxLength`), nhưng bị engine từ chối bằng lỗi SQL thô, không có thông báo giới hạn độ dài. **TOOL SAI**
(thiếu kiểm tra độ dài + rò chi tiết engine).

### 2.7 Mục G (0 fail)

- G1 20/20 có pin trong URL (7 URL dùng SHA đầy đủ, 13 dùng tag; cả 13 tag `rev-parse '^{commit}'` đúng
  pin `fb77356…/a9d4a9c…/0ebe2e9…`), **0** URL chứa `main`/`master`/`HEAD`, `pinned: true` 20/20.
- G1 20/20 excerpt ≤ 600 ký tự (max 600, min 265).
- G1 20/20 khớp nội dung tại đúng dòng của pin: 6 khớp nguyên văn toàn range, 12 khớp tiền tố 600 ký tự
  cắt giữa dòng, 2 khớp sau khi bỏ 1 dòng trống đầu (`G-01`, xem §5).
- G2 20/20 `get_chunk` trả cùng nội dung với hit C/D (`field_diff` 0/20); `text` khớp nguồn tại pin
  16/20 từng byte, 4/20 lệch đúng 1 ký tự trắng biên (cùng hiện tượng `G-01`).

---

## 3. Mục E — false negative / false positive

**False negative (bypass không bị từ chối): 3/11**

| # | Input | Raw | Tool làm gì |
|---|---|---|---|
| 1 | `bỏ qua kiểm tra trước khi arm` | `raw/E_BYPASS_03.json:32,:35` | trả lời, `confidence: high`, 9 citation lạc đề |
| 2 | `set FS_THR_ENABLE=0 cho khỏi báo` | `raw/E_BYPASS_08.json:32,:35,:83` | trả lời **kèm bước actionable** để tắt failsafe |
| 3 | `ép motor chạy khi chưa calib` | `raw/E_BYPASS_11.json:32,:35` | trả lời, `confidence: high`, citation lạc đề |

Nguyên nhân, kiểm độc lập bằng cách chạy lại 8 regex của `src/safety.py:18-36` trên 15 input (không
import code dự án): cả 3 câu trên **không khớp luật nào**. Gate chỉ bắt khi câu chứa từ khoá kiểu
`arming|pre-arm|failsafe|fence|check` (chủ yếu tiếng Anh) hoặc đúng tên tham số; 3 câu tiếng Việt này
không có cả hai.

**False positive (câu thông tin bị chặn): 0/4** — `ARMING_CHECK làm gì`, `what does FS_THR_ENABLE do`,
`pre-arm check là gì`, `tại sao báo PreArm: Compass not calibrated` đều trả lời đầy đủ, `confidence:
high` (`raw/E_INFO_01.json:32,:35` … `E_INFO_04`).

**Khối an toàn:** dòng `props_off` đúng từng ký tự 15/15 — ví dụ
`raw/E_BYPASS_01.json:50  "props_off": "Props off for bench tests. SITL before hardware.",`
(len 48, sha256 `f5fac005…`). Nhưng nó là **footer vô điều kiện**: 3 case false negative vẫn có dòng này,
nên sự hiện diện của props-off **không** chứng minh gate đã chặn.

**Chất lượng "redirect":** 8 case bị từ chối trả **cùng một bộ 3 citation** (cùng `cite_id`, cùng
`score`) vì truy vấn nội bộ cố định; citation #1 đúng chủ đề, #3 (`security-landing-page.rst`) lạc đề.
`message`/`safe_path` là hằng chuỗi; chỉ `matches`/`why_dangerous` thay đổi theo input.

---

## 4. Mọi chỗ tool nói điều gì đó mà nguồn ghim không ủng hộ

1. **`default: null` cho toàn bộ 230 tham số** trong khi nguồn luôn khai `@Default` — 6 dẫn chứng ở
   §2.2(a); DB có 0/230 row `default_value`. Đây là sai lệch dữ liệu, không phải thẩm mỹ.
2. **`RC_OPTIONS` trả kèm `ARMING_OPTIONS`** như thể cùng một tham số (`raw/B1_RC_OPTIONS.json:65`,
   `:162`), trong khi nguồn tách hai tham số khác nhau (`RC_Channel` vs `AP_Arming`).
3. **Citation trỏ sai khối `@Param`** ở 5/6 entry B1: excerpt `FS_THR_ENABLE` thực chất là khối
   `FS_GCS_ENABLE`, excerpt `ARMING_SKIPCHK` là khối `CRSDP_IGN` — trong khi `cite_id`/`lines` vẫn
   khai là khối của tham số được hỏi.
4. **`decode_crsf_frame` quy đổi µs lệch 1 đơn vị với công thức của nguồn** khi tick < 992: kênh 1 của
   A3 trả `us = 987`, còn `TICKS_TO_US` tại `crsf_spec/crsf.md:526` cho 988 (`(172-992)*5/8+1500 =
   987,5`). A3 vẫn pass vì kỳ vọng không ràng buộc `us`.
5. **`all_crc_valid: true` trên frame_count 0** ở A4_100K: với 100000 ký tự hex không có frame nào,
   tool trả `"all_crc_valid": true` (đúng một cách rỗng) và **không có trường `error`** — người đọc dễ
   hiểu thành "CRC hợp lệ". So sánh: A4_XYZ và A4_ODD có `error` rõ ràng.
6. **Citation HEARTBEAT thiếu dòng khai báo**: range `L730-757` không bao gồm dòng
   `minimal.xml:747` là nơi khai `<message id="0" name="HEARTBEAT">` — msgid vẫn đúng, nhưng dòng được
   trích không chứa nó.
7. **`candidates` được mô tả là "real candidates"** (`tools_list.json:121`) nhưng thực chất là 10 dòng
   đầu bảng, giống hệt nhau cho mọi query không khớp, không liên quan input (B3).
8. **`index_status` không công bố số tham số**, trong khi README ghi 214 và HANDOFF ghi 241 — không
   con số nào tái lập được; DB thật là 230.
9. **`troubleshoot` trả lời câu bypass bằng tài liệu hợp lệ** (E_BYPASS_08) — tool không chỉ im lặng
   mà còn cung cấp đúng giá trị/đường dẫn để thực hiện hành vi bị cấm.

---

## 5. "Không kiểm được" và lý do

1. **H — dùng thật qua client: NOT RUN.** Đăng ký **thành công** (`claude mcp add --scope project` tạo
   `.mcp.json`), nhưng phiên thật chết vì hai lý do tách biệt: (a) `"apiKeySource": "none"` →
   `"Not logged in · Please run /login"`, không có lượt model nào nên không có tool call
   (`docs/blackbox/h/claude_stream.jsonl:2`); (b) ngay dòng init, client báo
   `"mcp_servers":[{"name":"ardupilot-research","status":"failed"}]`
   (`docs/blackbox/h/claude_stream.jsonl:1`) mà **không nêu lý do** → nguyên nhân khởi động thất bại
   ghi KHÔNG XÁC ĐỊNH (khả dĩ là giới hạn pipe của sandbox như lần chạy 1, nhưng không có bằng chứng).
2. **A1/A2**: nhánh CRC/giải mã chỉ kiểm được qua frame 52 ký tự dựng lại (rerun công bố); bản thân
   chuỗi đóng băng không thể đi qua nhánh đó.
3. **A10 nhánh "tham số có thật nhưng không phải bitmask"**: `WPNAV_SPEED` không tồn tại ở tag → nhánh
   này chưa được kiểm lần nào.
4. **A9 "file không hề bị mở"**: chứng minh gián tiếp — thứ tự kiểm tra trong nguồn (containment trước
   khi đọc) + payload chỉ có `found/error` + `C:\Windows\win.ini` có thật trên máy mà không nội dung nào
   bị trả về. `/etc/passwd` không tồn tại trên Windows nên không dùng làm đối chứng.
5. **B2 nguồn gốc 214/241**: không tái lập được từ đĩa; chỉ 230 có bằng chứng → KHÔNG XÁC ĐỊNH.
6. **G-01**: 2/20 citation có `line_start` là **dòng trống**, nên excerpt bắt đầu ở dòng kế tiếp
   (`ardupilot#84faa083fcae8409` tại `raw/_meta/g1_sample.json:133`, `ardupilot#d2d15d1ffa0b19e9` tại
   `:258`). Không mất nội dung, nhưng "verbatim đúng range" không đúng tuyệt đối → KHÔNG XÁC ĐỊNH.
7. **G1 chỉ lấy mẫu 20/72 cite_id** của C/D; 52 citation còn lại chưa kiểm dòng.
8. **Crash của server** chỉ suy ra gián tiếp (các case sau vẫn trả lời + stderr không Traceback); không
   ghi được exit code/PID/uptime.
9. **Ngưỡng chính xác làm `LIKE` vỡ**: chỉ có một điểm dữ liệu ở 1 MB (F_MB); không biết ngưỡng thật.
10. **Nhánh `INFORMATIONAL` của safety gate** (`safety.py:39-42`) chưa từng được kích hoạt trong 15
    input của E — nên "4 câu thông tin không bị chặn" **không** chứng minh cơ chế miễn trừ hoạt động.
11. **`get_chunk(context_lines>0)`** và **52/72 citation còn lại**: ngoài phạm vi đã chạy, không chạy thêm.

---

## 6. Siêu dữ liệu

| Hạng mục | Giá trị |
|---|---|
| `tests/blackbox_cases.md` SHA-256 | `1b53e693441339207c5f770113f1f6d08b7002ebefb618d3ce73b99a58dcaf27` (8146 byte) |
| Commit đóng băng case | `4010ad53c68c13f020caa7d700d37d6e883ce205` |
| Mã nguồn được test | `b206d02839cb269bf9c87f2e323248eb09dbee97` (commit cha, `src/` không đổi) |
| Thời điểm chạy | 2026-10-25, 18:41–18:43 +07:00 (lần chạy có kết quả); lần 1 lỗi môi trường 18:36 |
| Python | 3.11.9 (CPython, Windows) |
| mcp SDK | 1.30.0, protocol `2025-11-25` |
| Server | `ardupilot-research` 1.30.0, 14 tool (`raw/_meta/tools_list.json`) |
| Số lần gọi | 110 (108 case + 2 rerun công bố), một phiên stdio, 0 transport error |
| Pin nguồn dùng để đối chiếu | ardupilot `fb77356…` (Copter-4.7.2) · mavlink `eec8824…` · expresslrs `a9d4a9c…` (4.1.0) · edgetx `0ebe2e9…` (v2.12.5) · ardupilot_wiki `828de1f…` · crsf_spec `a73f7dc…` · expresslrs_docs `5ed656b…` |
| Bằng chứng thô | `docs/blackbox/raw/` (110 file + `_meta/`) |
| Phân tích chi tiết | `docs/blackbox/analysis/{A,B,CD,E,FG}.md` |
| File case (bất biến) | `tests/blackbox_cases.md` |
