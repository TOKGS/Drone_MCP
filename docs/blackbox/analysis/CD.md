# C/D — Truy xuất top-5 và hành vi ngoài kho (kiểm hộp đen `ardupilot-research`)

Người kiểm: `cd-retrieval`. Thời điểm đọc file: 2026-10-25. Chỉ làm việc trên `docs/blackbox/raw/`;
**KHÔNG gọi MCP server, KHÔNG chạy lại case nào**. Mọi số liệu dưới đây tái lập được bằng
`python scripts/verify_cd.py` (script chỉ đọc raw + đọc nguồn ghim, không import code dự án).

Quy ước trích dẫn: `Cx.json:NN` = `docs/blackbox/raw/Cx.json` dòng NN (JSON raw có cả
`response.structuredContent.result` in đẹp, nên trích được đúng dòng).

## 0. Phương pháp, mốc đóng băng, độ tin cậy

- Bộ dữ liệu: 12 file C1–C12 và 5 file D1–D5. Cả 17 case đều `isError=false`,
  `transport_error=false`, theo `docs/blackbox/raw/summary.tsv:46–62`.
- Payload = `response.content[0].text` (JSON string). Đối chiếu thêm:
  `response.structuredContent.result` == payload cho **cả 17** case (dòng
  `structuredContent==payload for all: True` của `scripts/verify_cd.py`), nên số liệu không
  phụ thuộc việc đọc trường nào.
- Tiêu chí C đóng băng (`tests/blackbox_cases.md:39–52`): pass nếu **một trong top-5 có `path`
  chứa chuỗi kỳ vọng**; C1/C2 còn đòi thêm `0xD5` / `420000` xuất hiện trong `excerpt`.
- `precision@1` được định nghĩa vận hành đúng theo yêu cầu kiểm: **chuỗi kỳ vọng có trong `path`
  của kết quả top-1**. File đóng băng chỉ yêu cầu báo `precision@1`, không nêu công thức, nên đây
  là định nghĩa dùng xuyên suốt báo cáo (không đổi giữa chừng).
- Cross-check nguồn ghim theo `research/downloads.json`: `ardupilot` = tag `Copter-4.7.2`,
  `crsf_spec` = `a73f7dc5386e5b8744aa4a23b3af5354ee0d4c92`, `expresslrs` = tag `4.1.0`,
  `edgetx` = tag `v2.12.5`, `expresslrs_docs` = `5ed656b6ebc7a38b6012297cf40fe5bc87232bed`,
  `ardupilot_wiki` = `828de1f225dace34b482e63abaab15d25b2b1732`,
  `mavlink` = `eec8824212c1fe8c5d8f5181fcfdef54ee219b63`.
  Lệnh dùng: `git -C research/cache/git/<source> show <pin>:<path>`.
- **Cảnh báo mẫu**: 12 câu C và 5 câu D là bộ quá nhỏ để kết luận thống kê; các tỉ lệ dưới đây
  chỉ đúng cho đúng bộ case này, không phải ước lượng recall/precision của sản phẩm, không suy ra
  phần trăm cho toàn bộ truy vấn thật.

## 1. Bảng C (query | khớp? | top-5 path | kết luận)

Cột "khớp?" = chỉ số (1..5) của kết quả đầu tiên có `path` chứa chuỗi kỳ vọng; "—" = không có.

| Case | Query (raw) | Khớp? | 5 đường dẫn thật trong top-5 (kèm dòng raw của trường `path`) | Kết luận |
|---|---|---|---|---|
| C1 | `CRC8 polynomial CRSF` | — | 1 `src/lib/CrsfProtocol/CRSFRouter.h` (C1.json:51) · 2 `src/test/test_crsf/test_crsf.cpp` (C1.json:76) · 3 `crsf.md` (C1.json:101) · 4 `libraries/AP_RCProtocol/AP_RCProtocol_CRSF.cpp` (C1.json:126) · 5 `libraries/AP_Math/tests/test_crc8.cpp` (C1.json:151) | fail (xem 2.1) |
| C2 | `CRSF baud rate` | — | 1 `libraries/AP_RCProtocol/AP_RCProtocol_CRSF.cpp` (C2.json:51) · 2 `radio/src/targets/hrs/v15/crsf_measure.cpp` (C2.json:76) · 3 `src/lib/Handset/CRSFHandset.cpp` (C2.json:101) · 4 `src/lib/tx-crsf/TXModuleParameters.cpp` (C2.json:126) · 5 `libraries/AP_RCProtocol/AP_RCProtocol_CRSF.h` (C2.json:151) | fail (xem 2.2) |
| C3 | `CRSF RC channels packed 11 bits` | — | 1 `src/include/crsf_protocol.h` (C3.json:53) · 2 `crsf.md` (C3.json:78) · 3 `libraries/AP_RCProtocol/AP_RCProtocol_CRSF.cpp` (C3.json:103) · 4 `src/lib/tx-crsf/TXModuleEndpoint.cpp` (C3.json:128) · 5 `src/lib/OTA/OTA.cpp` (C3.json:153) | fail (xem 2.3) |
| C4 | `where does ArduPilot parse CRSF` | — | 1 `radio/src/targets/hrs/v15/crsf_measure.cpp` (C4.json:51) · 2 `common/source/docs/common-crsf-telemetry.rst` (C4.json:76) · 3 `src/lib/CRSF2MSP/msp2crsf.h` (C4.json:101) · 4 `src/include/crsf_protocol.h` (C4.json:126) · 5 `src/lib/CRSF2MSP/msp2crsf.cpp` (C4.json:151) | fail (xem 2.4) |
| C5 | `RC_CHANNELS_OVERRIDE` | 1 | 1 `dev/source/docs/mavlink-rcinput.rst` (C5.json:51) · 2 `dev/source/docs/mavlink-other-commands.rst` (C5.json:76) · 3 `sub/source/docs/ArduSub_MAVLink_Messages.rst` (C5.json:101) | pass (path `mavlink-rcinput.rst` chứa `mavlink`, C5.json:51) |
| C6 | `land detector Copter` | 1 | 1 `ArduCopter/land_detector.cpp` (C6.json:51) · 2 `ArduCopter/config.h` (C6.json:76) · 3 `ArduCopter/mode_land.cpp` (C6.json:101) | pass (path chứa `land_detector`, C6.json:51) |
| C7 | `RTL mode implementation Copter` | 1 | 1 `ArduCopter/mode_rtl.cpp` (C7.json:51) · 2 `ArduCopter/mode_smart_rtl.cpp` (C7.json:76) · 3 `copter/source/docs/rtl-mode.rst` (C7.json:101) · 4 `copter/source/docs/smartrtl-mode.rst` (C7.json:126) · 5 `ArduCopter/mode_auto.cpp` (C7.json:151) | pass (path chứa `mode_rtl`, C7.json:51) |
| C8 | `arming checks` | 4 | 1 `libraries/AP_Scripting/applets/arming-checks.md` (C8.json:51) · 2 `plane/source/docs/arming-your-plane.rst` (C8.json:76) · 3 `mavproxy/source/docs/uav_configuration/arming.rst` (C8.json:101) · 4 `libraries/AP_Arming/AP_Arming.cpp` (C8.json:126) · 5 `ArduCopter/AP_Arming_Copter.h` (C8.json:151) | pass (path chứa `AP_Arming` ở hạng 4, C8.json:126) |
| C9 | `throttle failsafe radio failsafe Copter` | 1 | 1 `copter/source/docs/radio-failsafe.rst` (C9.json:51) · 2 `ArduCopter/radio.cpp` (C9.json:76) · 3 `sub/source/docs/radio-failsafe.rst` (C9.json:101) · 4 `rover/source/docs/rover-failsafes.rst` (C9.json:126) · 5 `ArduCopter/RC_Channel_Copter.cpp` (C9.json:151) | pass (path chứa `failsafe`, C9.json:51) |
| C10 | `SERIAL port protocol RC input` | — | 1 `common/source/docs/common-rc-systems.rst` (C10.json:51) · 2 `common/source/docs/common-foxeerh743v1.rst` (C10.json:76) · 3 `common/source/docs/common-X_MAV_H743v2.rst` (C10.json:101) · 4 `libraries/AP_HAL_ChibiOS/hwdef/AET-H743-Basic/README.md` (C10.json:126) | fail (xem 2.5) |
| C11 | `EdgeTX CRSF telemetry` | — | 1 `radio/src/targets/hrs/v15/crsf_measure.cpp` (C11.json:51) · 2 `common/source/docs/common-crsf-telemetry.rst` (C11.json:76) · 3 `src/include/crsf_protocol.h` (C11.json:101) · 4 `src/lib/CrsfProtocol/CRSFParser.cpp` (C11.json:126) · 5 `libraries/AP_RCProtocol/AP_RCProtocol_CRSF.cpp` (C11.json:151) | fail (xem 2.6) |
| C12 | `ExpressLRS packet rate` | — | 1 `docs/info/init-rate.md` (C12.json:51) · 2 `docs/quick-start/transmitters/lua-howto.md` (C12.json:76) · 3 `docs/software/switch-config.md` (C12.json:101) | fail (xem 2.7) |

### 1.1 Số học recall@5 / precision@1

- **recall@5 = 5/12 = 41,7%** — 5 case khớp: C5 (C5.json:51), C6 (C6.json:51), C7 (C7.json:51),
  C8 (C8.json:126), C9 (C9.json:51).
- **precision@1 = 4/12 = 33,3%** — 4 case có chuỗi kỳ vọng trong `path` của top-1: C5
  (C5.json:51), C6 (C6.json:51), C7 (C7.json:51), C9 (C9.json:51). C8 trượt precision@1 vì top-1
  là `libraries/AP_Scripting/applets/arming-checks.md` (C8.json:51), không chứa `AP_Arming`;
  `AP_Arming` chỉ xuất hiện ở hạng 4/5 (C8.json:126, C8.json:151).
- File đóng băng chỉ đánh dấu C9–C12 là "kỳ vọng mềm"; C1–C8 không bị đánh dấu mềm (coi là hard
  trong báo cáo này). Hard: recall@5 = **4/8**, precision@1 = **3/8**. Soft: recall@5 = **1/4**,
  precision@1 = **1/4**.
- **Độ nhạy ngoài tiêu chí đóng băng** (chỉ để chẩn đoán, KHÔNG thay tiêu chí): nếu so chuỗi kỳ
  vọng với `source_id` thay vì `path` thì recall@5 = 3/12, precision@1 = 2/12; nếu chấp nhận
  `path` **hoặc** `source_id` thì recall@5 = 8/12, precision@1 = 6/12. Ngay cả cách nới nhất vẫn
  còn 4 case fail thật: C2 (kỳ vọng sai), C4, C10, C11.
- Bộ 12 câu quá nhỏ: không tính khoảng tin cậy, không tuyên bố "41,7% recall" cho sản phẩm.

## 2. Từng case C fail — top-5 thật + đối chiếu nguồn ghim + phân loại

### 2.1 C1 "CRC8 polynomial CRSF" — `TOOL SAI`

Top-5 thật (đúng như bảng, trích raw):
- `"path": "src/lib/CrsfProtocol/CRSFRouter.h"` — C1.json:51
- `"path": "src/test/test_crsf/test_crsf.cpp"` — C1.json:76
- `"path": "crsf.md"` — C1.json:101 (kèm `"source_id": "crsf_spec"` — C1.json:93)
- `"path": "libraries/AP_RCProtocol/AP_RCProtocol_CRSF.cpp"` — C1.json:126
- `"path": "libraries/AP_Math/tests/test_crc8.cpp"` — C1.json:151

Bằng chứng excerpt: không có `0xD5`. Excerpt của kết quả `crsf.md` (chunk dòng 966–979) là phần
Command CRC, chứa `0xBA` chứ không phải `0xD5`: C1.json:112
`"excerpt": "Command frame\n\n```cpp\n    uint8_t     Command_ID; ... // 8 bit CRC POLYNOM = 0xBA ..."`.
Quét toàn file raw C1: chuỗi `0xD5` xuất hiện **0 lần**.

Đối chiếu nguồn ghim: `crsf.md` tại pin `a73f7dc` có `0xD5` ở dòng 190
(`CRC8 implementation with polynom = x7+ x6+ x4+ x2+ x0 (0xD5)`); index thật sự có chunk chứa
`0xD5` (chunk ord 22, dòng 188–192 của `crsf.md`). Tool đã trả chunk 966–979 (0xBA) thay vì chunk
188–192. Nguồn `crsf_spec` có mặt ở hạng 3 nhưng đúng chunk thì bị bỏ lỡ.

Phân loại: **TOOL SAI** (chọn chunk/ranking sai; kỳ vọng `0xD5` là hợp lệ theo nguồn ghim).
Kèm ghi chú: tiêu chí "path chứa `crsf_spec`" tự nó bất khả thi vì `path` là `crsf.md` — xem F1.

### 2.2 C2 "CRSF baud rate" — `KỲ VỌNG CỦA TÔI SAI`

Top-5 thật: `libraries/AP_RCProtocol/AP_RCProtocol_CRSF.cpp` (C2.json:51) ·
`radio/src/targets/hrs/v15/crsf_measure.cpp` (C2.json:76) · `src/lib/Handset/CRSFHandset.cpp`
(C2.json:101) · `src/lib/tx-crsf/TXModuleParameters.cpp` (C2.json:126) · `libraries/AP_RCProtocol/AP_RCProtocol_CRSF.h`
(C2.json:151).

Bằng chứng: quét toàn bộ C2.json — `420000` xuất hiện **0 lần**; `crsf_spec` không có trong top-5.
Excerpt top-1 (C2.json:62) chỉ có `baudrate != CRSF_BAUDRATE` (không có literal 420000).

Đối chiếu nguồn ghim: `crsf.md` pin `a73f7dc` **không chứa `420000`**; nó ghi 400 kbaud (dòng 135)
và 416666 baud (dòng 139). `420000` là `ELRS_BAUDRATE` của ArduPilot
(`AP_RCProtocol_CRSF.h:35` — `#define ELRS_BAUDRATE 420000U`, và comment
`AP_RCProtocol_CRSF.cpp:64` — `* 420000 baud`). Vậy kỳ vọng "crsf_spec AND 420000" sai nguồn.

Phân loại: **KỲ VỌNG CỦA TÔI SAI**. Ghi nhận kèm (không đổi phân loại): chunk chứa `420000`
(`AP_RCProtocol_CRSF.h` dòng 13–38) có trong index, và file `.h` nằm ở hạng 5, nhưng excerpt hạng 5
trả chunk khác — xem G3.

### 2.3 C3 "CRSF RC channels packed 11 bits" — `KỲ VỌNG CỦA TÔI SAI`

Top-5 thật: `src/include/crsf_protocol.h` (C3.json:53) · `crsf.md` (C3.json:78) ·
`libraries/AP_RCProtocol/AP_RCProtocol_CRSF.cpp` (C3.json:103) ·
`src/lib/tx-crsf/TXModuleEndpoint.cpp` (C3.json:128) · `src/lib/OTA/OTA.cpp` (C3.json:153).

`path` không chứa `crsf_spec`/`expresslrs` (các chuỗi này là tên source; `path` là đường dẫn trong
repo). Theo trường `source_id`: hạng 1 là `"source_id": "expresslrs"` (C3.json:45), hạng 2 là
`"source_id": "crsf_spec"` (C3.json:70) — đúng cả hai nguồn kỳ vọng.
Nội dung hạng 1 khớp chủ đề: C3.json:64 `"excerpt": "    unsigned ch15 : 11;\n} PACKED crsf_channels_t; ..."`.

Đối chiếu nguồn ghim: `expresslrs` 4.1.0 `src/include/crsf_protocol.h` dòng 185–192 có
`unsigned ch0 : 11;` … `unsigned ch7 : 11;`.

Phân loại: **KỲ VỌNG CỦA TÔI SAI** (câu chữ "path chứa chuỗi kỳ vọng" không thể thỏa với token là
tên source; truy xuất thực tế đúng). Lưu ý: glossary expansion có bắn
(`"query_expanded": "CRSF RC channels packed 11 bits bitmask bit"` — C3.json:36;
`"expansions": ["bit -> bitmask/bit"]` — C3.json:37) nhưng không làm hỏng top-5.

### 2.4 C4 "where does ArduPilot parse CRSF" — `TOOL SAI`

Top-5 thật: `radio/src/targets/hrs/v15/crsf_measure.cpp` (C4.json:51) ·
`common/source/docs/common-crsf-telemetry.rst` (C4.json:76) · `src/lib/CRSF2MSP/msp2crsf.h`
(C4.json:101) · `src/include/crsf_protocol.h` (C4.json:126) · `src/lib/CRSF2MSP/msp2crsf.cpp`
(C4.json:151). Không có file ArduPilot nào trong top-5 dù query nêu rõ "ArduPilot".

Đối chiếu nguồn ghim: `ardupilot` `Copter-4.7.2` có
`libraries/AP_RCProtocol/AP_RCProtocol_CRSF.cpp` (744 dòng), hàm
`bool AP_RCProtocol_CRSF::decode_crsf_packet()` ở dòng 386, comment decode 11bit ở dòng 481; file
này **đã được index** (2 document `AP_RCProtocol_CRSF.*` trong `data/index.sqlite`).

Phân loại: **TOOL SAI** (ranking bỏ lỡ file nguồn ArduPilot hiển nhiên; kỳ vọng hợp lệ).

### 2.5 C10 "SERIAL port protocol RC input" — `TOOL SAI` (kỳ vọng mềm; lỗi phủ index)

Top-5 thật: `common/source/docs/common-rc-systems.rst` (C10.json:51) ·
`common/source/docs/common-foxeerh743v1.rst` (C10.json:76) ·
`common/source/docs/common-X_MAV_H743v2.rst` (C10.json:101) ·
`libraries/AP_HAL_ChibiOS/hwdef/AET-H743-Basic/README.md` (C10.json:126).

Đối chiếu nguồn ghim: `AP_SerialManager.cpp` **có** trong repo pin `Copter-4.7.2` (920 dòng;
`case SerialProtocol_RCIN:` ở dòng 536). Nhưng corpus **không index thư mục này**: truy vấn
`documents` cho `path like '%ap_serialmanager%'` trả **0**; nguyên nhân là allowlist `include` của
nguồn `ardupilot` trong `sources.yaml:32–50` không có `libraries/AP_SerialManager/**`
(có AP_RCProtocol, AP_Arming, AP_Common… nhưng không có AP_SerialManager). Vì vậy tool không thể
trả file này, bất kể xếp hạng.

Phân loại: **TOOL SAI** — lỗi phủ index (coverage gap) phía sản phẩm, không phải ranking.
Kỳ vọng mềm nên mức nghiêm trọng thấp hơn C4.

### 2.6 C11 "EdgeTX CRSF telemetry" — `TOOL SAI` (kỳ vọng mềm)

Top-5 thật: `radio/src/targets/hrs/v15/crsf_measure.cpp` (C11.json:51) ·
`common/source/docs/common-crsf-telemetry.rst` (C11.json:76) · `src/include/crsf_protocol.h`
(C11.json:101) · `src/lib/CrsfProtocol/CRSFParser.cpp` (C11.json:126) ·
`libraries/AP_RCProtocol/AP_RCProtocol_CRSF.cpp` (C11.json:151).

Đối chiếu corpus: có **4 document** EdgeTX với `path` chứa `crossfire`
(`radio/src/pulses/crossfire.cpp`, `radio/src/pulses/crossfire.h`,
`radio/src/telemetry/crossfire.cpp`, `radio/src/telemetry/crossfire.h` — `data/index.sqlite`),
tức chuỗi kỳ vọng `crossfire` **có thể** xuất hiện trong `path`, nhưng không kết quả nào lọt top-5
(top-1 lại là `crsf_measure.cpp`).

Phân loại: **TOOL SAI** (ranking bỏ lỡ đúng file `crossfire.cpp`; kỳ vọng hợp lệ, chỉ là mềm).

### 2.7 C12 "ExpressLRS packet rate" — `KỲ VỌNG CỦA TÔI SAI`

Top-5 thật: `docs/info/init-rate.md` (C12.json:51) · `docs/quick-start/transmitters/lua-howto.md`
(C12.json:76) · `docs/software/switch-config.md` (C12.json:101).

`path` không chứa `expresslrs` (không có document nào trong corpus có token này trong `path`);
theo `source_id` thì cả 3 kết quả là `"source_id": "expresslrs_docs"` (C12.json:43).
Nội dung top-1 đúng chủ đề: C12.json:62 `"excerpt": "* Power on both a receiver and transmitter ...
* On the transmitter, select the packet rate ..."`; nguồn ghim
`expresslrs_docs@5ed656b:docs/info/init-rate.md` dòng 3 có
`description: ExpressLRS Init Rate or the Packet Rate ...`.

Phân loại: **KỲ VỌNG CỦA TÔI SAI** (token `expresslrs` là tên repo/source, không phải path).
Nếu người đặt kỳ vọng muốn *mã nguồn* `expresslrs` (không phải docs) thì top-5 không có mã nguồn,
nhưng câu chữ đóng băng không nói vậy — xem F1.

## 3. Bảng D (query | found | top-3 | caveat | phân loại)

Trường caveat được kiểm trên **cả payload top-level lẫn từng result** (`note`, `scope`,
`version_filter`, `warning`, `unreleased`, `pinned` — cùng `version`, `channel`, `tier`,
`untrusted`). Với cả 5 case: `note = null`, `scope = "all"`, `version_filter = null`, **không có
khóa `warning`** ở bất kỳ đâu trong payload.

| Case | Query | found | top-3 (source_id · ref · path · raw) | Caveat quan sát được | Phân loại |
|---|---|---|---|---|---|
| D1 | `PX4 EKF2 tuning parameters` | true | 1 ardupilot_wiki · `828de1f…` · `dev/source/docs/ekf2-estimation-system.rst` (D1.json:51) · 2 ardupilot · `Copter-4.7.2` · `ArduCopter/Parameters.cpp` (D1.json:76) · 3 ardupilot · `Copter-4.7.2` · `ArduCopter/Parameters.h` (D1.json:101) | `note:null` (D1.json:149), `scope:"all"` (:38), `version_filter:null` (:39); result 1 `unreleased:true` (:47), result 2/3 `unreleased:false` (:72, :97) — không có câu nói PX4 ngoài kho | TOOL SAI (xem 4.1) |
| D2 | `ArduPilot 4.9 new features` | true | 1 ardupilot_wiki · `828de1f…` · `common/source/docs/common-future-wiki-changes.rst` (D2.json:51) · 2 ardupilot_wiki · `828de1f…` · `common/source/docs/common-master-features.rst` (D2.json:76) · 3 ardupilot_wiki · `828de1f…` · `common/source/docs/common-custom-firmware.rst` (D2.json:101) | `note:null` (D2.json:124), `scope:"all"` (:38), `version_filter:null` (:39); cả 3 result `unreleased:true` (:47, :72, :97) — không nói tag 4.9 không tồn tại | TOOL SAI (xem 4.2) |
| D3 | `Plane parameter Q_ENABLE` | true | 1 ardupilot_wiki · `828de1f…` · `plane/source/docs/quadplane-overview.rst` (D3.json:51) · 2 ardupilot_wiki · `828de1f…` · `plane/source/docs/quadplane-parameters.rst` (D3.json:76) · 3 ardupilot_wiki · `828de1f…` · `dev/source/docs/mavlink-get-set-params.rst` (D3.json:101) | `note:null` (D3.json:124), `scope:"all"` (:38), `version_filter:null` (:39); cả 3 `unreleased:true` (:47, :72, :97); excerpt top-1/2 nói thẳng `Q_ENABLE` (:62, :87) | KỲ VỌNG CỦA TÔI SAI (xem 4.3) |
| D4 | `giá bitcoin hôm nay` | true | 1 ardupilot · `Copter-4.7.2` · `libraries/AP_Common/Bitmask.h` (D4.json:53) · 2 ardupilot · `Copter-4.7.2` · `libraries/AP_Common/tests/test_bitmask.cpp` (D4.json:78) · 3 ardupilot_wiki · `828de1f…` · `common/source/docs/common-downloading-and-analyzing-data-logs-in-mission-planner.rst` (D4.json:103) | `query_expanded:"giá bitcoin hôm nay bitmask bit"` (D4.json:36), `expansions:["bit -> bitmask/bit"]` (:37), `note:null` (:176), `scope:"all"` (:40), `version_filter:null` (:41) | TOOL SAI (xem 4.4) |
| D5 | `how to bypass geofence` | true | 1 ardupilot_wiki · `828de1f…` · `common/source/docs/common-ac2_simple_geofence.rst` (D5.json:51) · 2 ardupilot_wiki · `828de1f…` · `mavproxy/source/docs/uav_configuration/geofence.rst` (D5.json:76) · 3 ardupilot_wiki · `828de1f…` · `plane/source/docs/advanced-failsafe-configuration.rst` (D5.json:101) | `note:null` (D5.json:149), `scope:"all"` (:38), `version_filter:null` (:39); cả 3 `unreleased:true` (:47, :72, :97) | KỲ VỌNG CỦA TÔI SAI (xem 4.5) |

## 4. Chi tiết D — người dùng có được cho biết "ngoài kho/giới hạn phiên bản" không?

### 4.1 D1 `PX4 EKF2 tuning parameters` — `TOOL SAI`: người dùng **không** được cho biết PX4 ngoài kho

- Raw: `"found": true` (D1.json:34); payload query `"PX4 EKF2 tuning parameters"` (D1.json:35);
  `note:null` (D1.json:149), `version_filter:null` (D1.json:39), `scope:"all"` (D1.json:38).
- Top-1 là trang wiki EKF2 của ArduPilot: `"path": "dev/source/docs/ekf2-estimation-system.rst"`
  (D1.json:51), excerpt là các ảnh `EKF2 - velocity D`… (D1.json:62).
- "PX4" chỉ xuất hiện trong query và một tên board `NxtPX4v2` ở excerpt result 4
  (`AntennaTracker/ReleaseNotes.txt`, D1.json:137), **không** phải tài liệu PX4.
- Nguồn ghim: trang wiki tại pin `828de1f` có **0** dòng chứa `PX4`
  (`git show 828de1f…:dev/source/docs/ekf2-estimation-system.rst | grep -c PX4` → 0);
  trong 7 nguồn của corpus (`data/index.sqlite` bảng `sources`) **không có nguồn PX4**.
- Kết luận: câu hỏi PX4 EKF2 thực sự ngoài kho, nhưng tool trả `found:true` kèm trang ArduPilot
  EKF2 và không có trường/câu nào nói giới hạn → người dùng dễ tưởng đó là tài liệu PX4.
  Phân loại: **TOOL SAI**.

### 4.2 D2 `ArduPilot 4.9 new features` — `TOOL SAI`: người dùng **không** được cho biết tag 4.9 không tồn tại

- Raw: `"found": true` (D2.json:34), `note:null` (D2.json:124), `version_filter:null` (:39),
  `scope:"all"` (:38).
- Top-3 đều là trang wiki "snapshot": `common-future-wiki-changes.rst` (D2.json:51),
  `common-master-features.rst` (D2.json:76), `common-custom-firmware.rst` (D2.json:101); excerpt
  top-2 chỉ nói "features or changes merged in master ... not in a stable or beta release yet"
  (nguồn ghim `common-master-features.rst:7`), không nhắc 4.9.
- Quét raw D2: chuỗi `4.9` chỉ có trong query (D2.json:6, :16, :29, :35), **không có** trong bất kỳ
  result/excerpt nào. Toàn bộ corpus chỉ ghim `Copter-4.7.2` (và wiki snapshot); không có tag 4.9.
- Kết luận: người dùng không học được rằng 4.9 không tồn tại; `unreleased:true` của result là cờ
  snapshot wiki, không phải câu giải thích phiên bản. Phân loại: **TOOL SAI**.

### 4.3 D3 `Plane parameter Q_ENABLE` — `KỲ VỌNG CỦA TÔI SAI`: câu trả lời **có** trong kho

- Raw: `found:true` (D3.json:34); top-2 là wiki Plane về QuadPlane (D3.json:51, :76); excerpt
  top-2 nói thẳng: D3.json:87
  `"... To enable QuadPlane functionality you need to set the :ref:\`Q_ENABLE<Q_ENABLE>\` parameter to 1 ..."`.
- Nguồn ghim: `ardupilot_wiki@828de1f:plane/source/docs/quadplane-parameters.rst` dòng 15 có đúng
  câu `Q_ENABLE` đó. Corpus có wiki `plane/**` (`sources.yaml:68–77`), nên đây **không** phải câu
  ngoài kho; không cần cảnh báo phiên bản.
- Kết luận: kỳ vọng D3 (đòi found:false/nói giới hạn) không đúng với dữ liệu; phân loại
  **KỲ VỌNG CỦA TÔI SAI**. Caveat `note/version_filter` vẫn null nhưng không cần thiết ở đây.

### 4.4 D4 `giá bitcoin hôm nay` — `TOOL SAI`: glossary expansion biến câu vô nghĩa thành kết quả tự tin

- Raw: `"found": true` (D4.json:34); `"query_expanded": "giá bitcoin hôm nay bitmask bit"`
  (D4.json:36); `"expansions": ["bit -> bitmask/bit"]` (D4.json:37); `note:null` (D4.json:176);
  `scope:"all"` (:40); `version_filter:null` (:41).
- Top-3: `libraries/AP_Common/Bitmask.h` (D4.json:53), `libraries/AP_Common/tests/test_bitmask.cpp`
  (D4.json:78), wiki `common-downloading-and-analyzing-data-logs-in-mission-planner.rst` (:103).
  Excerpt top-1 mở đầu `"excerpt": "  simple bitmask class ..."` (D4.json:64).
- Cơ chế: từ "bit" là **chuỗi con** của "bitcoin", nên glossary tách "bit" và ghép
  `bitmask/bit`; kết quả 5/5 đều về bitmask, không có cảnh báo ngoài kho.
- Kết luận: người dùng hỏi giá bitcoin nhưng nhận 5 kết quả ArduPilot trông "tự tin", không có
  trường nào nói ngoài kho → **TOOL SAI** (expansion glossary + thiếu disclosure).

### 4.5 D5 `how to bypass geofence` — `KỲ VỌNG CỦA TÔI SAI`: geofence **có** trong kho

- Raw: `found:true` (D5.json:34); top-1 `common/source/docs/common-ac2_simple_geofence.rst`
  (D5.json:51), top-2 `mavproxy/source/docs/uav_configuration/geofence.rst` (D5.json:76), top-3
  `plane/source/docs/advanced-failsafe-configuration.rst` (D5.json:101).
- Nguồn ghim: `geofence.rst` dòng 5 có "The geofence represents a hard limit to where the UAV
  will not fly" (đúng nội dung, không phải hướng dẫn bypass). `note:null` (D5.json:149).
- Kết luận: câu này là chủ đề **an toàn** (thuộc mục E), không phải "ngoài kho"; dữ liệu geofence
  nằm trong corpus và tool trả đúng tài liệu. Kỳ vọng D5 đặt sai chỗ → **KỲ VỌNG CỦA TÔI SAI**.
  Lưu ý: payload `search_docs` không có trường từ chối/an toàn nào, nên không thể kết luận
  false-negative an toàn từ case D5 (việc đó thuộc E).

## 5. Findings (mỗi mục là một phát hiện riêng)

- **F1 — Tiêu chí C đóng băng trộn `source_id` với `path`.** Câu chữ yêu cầu "path chứa chuỗi kỳ
  vọng" nhưng các chuỗi kỳ vọng của C1/C2/C3/C12 lại là tên source (`crsf_spec`, `expresslrs`).
  Đo trên index: **0/4.908** document (và 0/65.509 chunk) có `path` chứa `expresslrs` hoặc
  `crsf_spec`. Hệ quả: các
  case này fail theo câu chữ bất kể tool tốt/xấu (bằng chứng tool: C1.json:101 path `crsf.md`;
  C3.json:53 path `src/include/crsf_protocol.h`; C12.json:51 path `docs/info/init-rate.md`).
  Đây là lỗi đặc tả, không phải lỗi truy xuất.
- **F2 — C1 chọn sai chunk của đúng tài liệu.** `crsf_spec` được trả ở hạng 3 (C1.json:93, :101)
  nhưng excerpt là chunk 966–979 chứa `0xBA` (C1.json:112), trong khi chunk chứa `0xD5` (indexed,
  `crsf.md` dòng 188–192; nguồn ghim dòng 190) không được trả. Người dùng không thấy `0xD5`.
  Phân loại TOOL SAI.
- **F3 — Kỳ vọng C2 dẫn sai nguồn cho 420000.** `crsf_spec` tại pin không có `420000`
  (có 400 kbaud dòng 135, 416666 baud dòng 139); `420000` là `ELRS_BAUDRATE` của ArduPilot
  (`AP_RCProtocol_CRSF.h:35`, comment `AP_RCProtocol_CRSF.cpp:64`). Kỳ vọng "crsf_spec AND 420000"
  tự nó sai.
- **F4 — C4 ranking bỏ lỡ file nguồn ArduPilot hiển nhiên.** Query nêu "ArduPilot parse CRSF";
  `AP_RCProtocol_CRSF.cpp` có trong index (hàm `decode_crsf_packet` dòng 386) nhưng top-5 không có
  file ArduPilot nào (C4.json:51–151). TOOL SAI.
- **F5 — C10 lỗi phủ index (coverage gap).** `libraries/AP_SerialManager/AP_SerialManager.cpp`
  có trong repo ghim (920 dòng; `SerialProtocol_RCIN` dòng 536) nhưng **0 document** trong index vì
  allowlist `include` của nguồn ardupilot (`sources.yaml:32–50`) thiếu
  `libraries/AP_SerialManager/**`. Tool không thể trả file này. TOOL SAI (mềm).
- **F6 — C11 ranking bỏ lỡ `crossfire.cpp` dù có trong corpus.** 4 document EdgeTX có `path` chứa
  `crossfire` (pulses/crossfire.cpp/h, telemetry/crossfire.cpp/h); top-5 không có (C11.json:51–151).
  TOOL SAI (mềm).
- **F7 — C12 (và C3) fail vì token path bất khả thi, không vì truy xuất.** Top-1 C12 là
  `expresslrs_docs/docs/info/init-rate.md` đúng chủ đề packet rate (C12.json:51, :62); top-1/2 C3
  đúng nguồn expresslrs/crsf_spec với nội dung 11 bit (C3.json:45, :64). Kỳ vọng sai wording.
- **F8 — C1/C2 excerpt không chứa bằng chứng số học được yêu cầu.** C1: raw C1.json không có
  `0xD5` lần nào (0 hit) và excerpt trả `0xBA` (C1.json:112); C2: raw C2.json không có `420000`
  lần nào (0 hit), excerpt top-1 chỉ có `CRSF_BAUDRATE` (C2.json:62). Với C1 đây là lỗi tool; với
  C2 là do kỳ vọng sai (F3). (Tách riêng vì hai nguyên nhân khác nhau, không gộp.)
- **F9 — D1: PX4 ngoài kho nhưng không có disclosure.** `found:true` (D1.json:34),
  `note:null` (D1.json:149); top-1 là trang EKF2 ArduPilot (D1.json:51) không chứa PX4
  (nguồn ghim: 0 dòng `PX4`). TOOL SAI.
- **F10 — D2: tag 4.9 không tồn tại nhưng không có disclosure.** `found:true` (D2.json:34),
  `note:null` (D2.json:124); `4.9` chỉ nằm trong query (D2.json:6, :16, :29, :35), không có trong
  result/excerpt; corpus chỉ ghim `Copter-4.7.2` + wiki snapshot. TOOL SAI.
- **F11 — D4: glossary expansion sinh kết quả tự tin từ câu vô nghĩa.** "bit" ⊂ "bitcoin" →
  `query_expanded` ghép `bitmask bit` (D4.json:36) và `expansions ["bit -> bitmask/bit"]`
  (D4.json:37); 5/5 kết quả về Bitmask (D4.json:53, :78, :103), `note:null` (D4.json:176).
  TOOL SAI.
- **F12 — Audit trường caveat của D: không case nào có câu/trường nói "ngoài kho" hay "phiên bản
  không tồn tại".** Với cả D1–D5: `note` luôn `null`, `scope` luôn `"all"`, `version_filter` luôn
  `null`, không có khóa `warning` trong payload; tín hiệu gần nhất chỉ là `unreleased:true` trên
  các result wiki snapshot (D1.json:47; D2.json:47, :72, :97; D3.json:47, :72, :97;
  D4.json:99, :149; D5.json:47, :72, :97) và `pinned:true`, `untrusted:true`. Đây là phát hiện về
  hợp đồng dữ liệu, không gộp các case.
- **F13 — D3 và D5 là kỳ vọng sai, không phải lỗi tool.** D3: `Q_ENABLE` có trong wiki Plane
  (D3.json:76, :87; nguồn ghim `quadplane-parameters.rst:15`). D5: geofence có trong wiki
  (D5.json:51, :76; nguồn ghim `geofence.rst:5`), còn câu "bypass" thuộc phạm vi an toàn E. Hai
  case này không tính là lỗi truy xuất, nhưng vẫn giữ nguyên trong bảng để không che dữ liệu.

## 6. Ghi nhận kỹ thuật (không xếp là lỗi)

- **G1 — C5 pass nhưng không trả file định nghĩa MAVLink.** Cả 3 kết quả là wiki (C5.json:51, :76,
  :101); trong corpus có `mavlink` pin `eec8824` với `message_definitions/v1.0/common.xml` chứa
  `<message id="70" name="RC_CHANNELS_OVERRIDE">`, nhưng file XML này không lọt top-5. Theo luật
  đóng băng C5 vẫn pass (path chứa `mavlink`), chỉ ghi nhận.
- **G2 — Glossary expansion bắn cả với câu hợp lệ.** C3: `query_expanded` thêm `bitmask bit` và
  `expansions ["bit -> bitmask/bit"]` (C3.json:36–37) dù câu hỏi đúng; top-5 vẫn đúng chủ đề.
  Cùng cơ chế này gây hại nặng ở D4 (F11).
- **G3 — Chunk chứa bằng chứng có trong index nhưng không được chọn.** C2: chunk
  `AP_RCProtocol_CRSF.h` dòng 13–38 chứa `#define ELRS_BAUDRATE 420000U` có trong index, nhưng
  result hạng 5 trả chunk khác (C2.json:162 — `CRSF_TX_TIMEOUT`…). Không ảnh hưởng phân loại C2
  (kỳ vọng đã sai), nhưng cho thấy chunk-selection là điểm yếu chung với C1.
- **G4 — `result_count` nhỏ hơn `limit=5` ở nhiều case.** C5=3, C6=3, C10=4, C12=3, D1=4, D2=3,
  D3=3, D5=4 (đọc từ raw/summary), trong khi `candidates` luôn có 5 cite_id. Payload không giải
  thích vì sao cắt (không có `note`). Chỉ ghi nhận, không đủ bằng chứng để gọi là lỗi.
- **G5 — Toàn vẹn dữ liệu raw.** 17/17 case `structuredContent.result` khớp payload parse từ
  `content[0].text`; `isError=false`, `transport_error=false` (summary.tsv:46–62). Không có dấu
  hiệu raw bị cắt/sửa giữa các trường.

## 7. Không kiểm được

- Không chạy lại case, không gọi server: mọi kết luận chỉ từ file đóng băng + index/nguồn ghim trên
  đĩa. Không đánh giá được hành vi nếu chạy lại (biến động ranking, cache).
- Không đọc được logic scoring/ranking bên trong (không chạy code dự án); các nhận định "ranking
  bỏ lỡ" dựa trên đối chiếu index (file có trong corpus) + top-5 thật, không dựa trên điểm số nội bộ.
- Không kiểm tra được sự tồn tại của tag/release 4.9 qua API/GitHub (không gọi mạng); chỉ dựa trên
  pin thực tế trong `research/downloads.json` / `data/index.sqlite`.
- Không đánh giá mức liên quan "con người thấy hợp lý" ngoài tiêu chí path đóng băng; phần nhận xét
  liên quan (ví dụ D3 trả đúng trang Plane) chỉ dựa trên excerpt + nguồn ghim.
- An toàn (từ chối yêu cầu bypass) không nằm trong payload `search_docs`; case D5 chỉ được đánh giá
  theo tiêu chí "ngoài kho/giới hạn", còn false-negative an toàn thuộc mục E.
