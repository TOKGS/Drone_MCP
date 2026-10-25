# B — `lookup_param` (B1/B2/B3) đối chiếu nguồn ghim `Copter-4.7.2`

Người thực hiện: teammate `b-params` · task `task-2` · ngày 2026-10-25.

**Luật đã tuân thủ:** chỉ đọc file trên đĩa (`docs/blackbox/raw/`, `data/index.sqlite`,
`research/cache/git/ardupilot`); **KHÔNG** gọi MCP server, **KHÔNG** chạy lại case nào;
**KHÔNG** sửa `src/`, `tests/`, `tests/blackbox_cases.md`. Script kiểm chứng:
[`scripts/verify_b.py`](../../../scripts/verify_b.py) (stdlib, không import code dự án).

**Pin:** `git -C research/cache/git/ardupilot show fb773567896014da007bca58358704d4a0d8516f:<path>`
(tag `Copter-4.7.2`, commit `fb773567896014da007bca58358704d4a0d8516f`).

**Quy ước trích dẫn (quan trọng):** trong mỗi file raw, toàn bộ payload JSON nằm trên **một
dòng** (chuỗi escape) — `"text": "..."`. Với mọi `B1_*`/`B3_*` dòng đó là **dòng 27**; với
`B2_INDEX_STATUS.json` là **dòng 23**. Vì vậy ký hiệu `raw/B1_X.json:27` là "payload của case
B1_X, nằm tại dòng 27". Khi trích payload tôi trích bản đã decode từ đúng dòng đó. Nguồn ghim
được trích theo `git show fb77356:<path>` với **số dòng của file nguồn**.

---

## 1. B1 — 10 tên tham số

### 1.1 Bảng tổng hợp

| # | Tên | tool `found` | tool trích (path:lines) | nguồn ghim nói gì | kết luận trường | verdict / 3 trạng thái |
|---|-----|--------------|--------------------------|-------------------|-----------------|------------------------|
| 1 | `FS_THR_ENABLE` | **true**, `resolved_by=exact` | `ArduCopter/Parameters.cpp#L95-L145` (`cite_id ardupilot#aff614bd8d1d5b3d`) | khối `@Param: FS_THR_ENABLE` tại **L124-129**; mô tả/`@Values` khớp; default `FS_THR_ENABLED_ALWAYS_RTL` (=1) | mô tả ✓, values ✓, units/range `null` ✓ (nguồn không có), **default `null` ≠ 1**, excerpt **không** chứa khối (xem §4 E5) | **TOOL SAI** (thiếu default; excerpt lệch khối) |
| 2 | `FS_THR_VALUE` | **true**, `exact` | `ArduCopter/Parameters.cpp#L95-L145` | khối tại **L131-138**: `@Range: 910 1100`, `@Units: PWM`, default `FS_THR_VALUE_DEFAULT` (=975) | mô tả/units/range ✓; **default `null` ≠ 975**; excerpt lệch khối | **TOOL SAI** (thiếu default; excerpt lệch khối) |
| 3 | `RC_OPTIONS` | **true**, `resolved_by=suffix`, **2 params** | #1 `libraries/RC_Channel/RC_Channels_VarInfo.h#L84-L117`; #2 `libraries/AP_Arming/AP_Arming.cpp#L141-L179` | #1 = khối `@Param: _OPTIONS` **L92-97** (đúng RC_OPTIONS, prefix `RC` tại `Parameters.cpp:694`); #2 = khối `@Param: OPTIONS` **L162-167** → tên đầy đủ **`ARMING_OPTIONS`** (prefix `ARMING_` tại `Parameters.cpp:240`), **không phải RC_OPTIONS** | #1 khớp display/desc/bitmask 0..13; #2 là **false positive**; **default #1 `null` ≠ `(1U<<5)`=32** | **TOOL SAI** (trả thêm tham số khác; thiếu default) |
| 4 | `RC_PROTOCOLS` | **true**, `suffix` | `libraries/RC_Channel/RC_Channels_VarInfo.h#L84-L117` | khối `@Param: _PROTOCOLS` **L100-105**; desc/`@Bitmask` khớp; default `1` | mô tả ✓, bitmask 0..16,18 ✓; **default `null` ≠ 1**; excerpt lệch khối | **TOOL SAI** (thiếu default; excerpt lệch khối) |
| 5 | `SERIAL1_PROTOCOL` | **false** | — (không trích) | **CÓ thật**: `libraries/AP_SerialManager/AP_SerialManager.cpp:183-191` (`@Param: 1_PROTOCOL`, prefix `SERIAL` tại `libraries/AP_Vehicle/AP_Vehicle.cpp:283-287`); `Tools/autotest/default_params/vee-gull_005.param:518` ghi `SERIAL1_PROTOCOL,1`; `libraries/AP_DroneCAN/AP_DroneCAN.cpp:214` `@CopyFieldsFrom: SERIAL1_PROTOCOL` | tool báo `"found": false, "params": []` + candidates rác | **TOOL SAI** (bỏ sót tham số có thật) |
| 6 | `ARMING_CHECK` | **false** | — | **KHÔNG tồn tại** ở tag: `ArduCopter/ReleaseNotes.txt:651-654` "ARMING_CHECK replaced with ARMING_SKIPCHK"; `libraries/AP_Arming/AP_Arming.cpp:160,228` (`index 8 was CHECK ... became SKIPCHK` / `PARAM_CONVERSION - 4.7 CHECK -> SKIPCHK`) | tool trả `found:false` | **KỲ VỌNG CỦA TÔI SAI** (tool đúng) |
| 7 | `ARMING_SKIPCHK` | **true**, `suffix` | `libraries/AP_Arming/AP_Arming.cpp#L178-L205` | khối `@Param: SKIPCHK` **L195-201**; display/desc/bitmask khớp (1..8,10..19, không có bit 9); default `0` | display/desc/bitmask ✓; **default `null` ≠ 0**; excerpt lệch khối | **TOOL SAI** (thiếu default; excerpt lệch khối) |
| 8 | `LOG_BITMASK` | **true**, `exact` | `ArduCopter/Parameters.cpp#L199-L232` | khối `@Param: LOG_BITMASK` **L207-212**, desc/bitmask khớp; default `DEFAULT_LOG_BITMASK` (`ArduCopter/config.h:547-562`) | display/desc/bitmask ✓; excerpt **có** chứa khối; **default `null` ≠ macro** | **TOOL SAI** (thiếu default) |
| 9 | `BATT_FS_LOW_ACT` | **false** | — | **CÓ thật**: `libraries/AP_BattMonitor/AP_BattMonitor_Params.cpp:143-153` (`@Param: FS_LOW_ACT`, default `0`), prefix ghép `BATT` + `_` (`ArduCopter/Parameters.cpp:401-403`, `libraries/AP_BattMonitor/AP_BattMonitor.cpp:55` `AP_SUBGROUPINFO(_params[0], "_", ...)`); `Tools/Frame_params/3DR_Iris+.param:27` ghi `BATT_FS_LOW_ACT,2` | tool báo `found:false` + candidates rác | **TOOL SAI** (bỏ sót tham số có thật) |
| 10 | `WPNAV_SPEED` | **false** | — | **KHÔNG tồn tại** ở tag: đã đổi thành **`WP_SPD`** — `libraries/AC_WPNav/AC_WPNav.cpp:49,56` (`@Param: SPD`, `AP_GROUPINFO("SPD",14,...)`), `:141` "old WPNAV_SPEED at index 0" → `WP_SPD`, prefix `WP_` tại `ArduCopter/Parameters.cpp:369` | tool trả `found:false` | **KỲ VỌNG CỦA TÔI SAI** (tool đúng) |

**Danh sách tên tool nói "không có" nhưng grep nguồn ghim LẠI CÓ** (yêu cầu riêng của B1):
**`SERIAL1_PROTOCOL`**, **`BATT_FS_LOW_ACT`** — trích dẫn grep ở §4 E9/E10.
Hai tên còn lại tool nói `found:false` là `ARMING_CHECK`, `WPNAV_SPEED` — grep **không** thấy
khai báo ở tag (chỉ còn trong ReleaseNotes/comments), nên tool đúng.

### 1.2 So khớp từng trường của các entry `found:true`

Nguồn: `git show fb77356:<path>`; mọi trường của tool đọc từ payload tại `raw/B1_<NAME>.json:27`.

| tên (entry) | khối nguồn | `display_name` | `description` | `units` | `range` | `values` | `bitmask` | `default` tool vs nguồn |
|---|---|---|---|---|---|---|---|---|
| FS_THR_ENABLE | Parameters.cpp:124-129 | khớp | khớp từng chữ | `null` = nguồn | `null` = nguồn | khớp 8 giá trị | nguồn không có | `null` vs `FS_THR_ENABLED_ALWAYS_RTL` (=**1**, defines.h:120) |
| FS_THR_VALUE | Parameters.cpp:131-138 | khớp | khớp | `"PWM"` = nguồn | `"910 1100"` = nguồn | nguồn không có | nguồn không có | `null` vs `FS_THR_VALUE_DEFAULT` (=**975**, config.h:307) |
| RC_OPTIONS (`_OPTIONS`) | RC_Channels_VarInfo.h:92-97 | khớp "RC options" | khớp "RC input options" | `null` = nguồn | `null` = nguồn | nguồn không có | khớp đủ 14 bit 0..13 | `null` vs `(uint32_t)RC_Channels::Option::ARMING_CHECK_THROTTLE` = **1U<<5 = 32** (RC_Channel.h:670) |
| RC_OPTIONS (`OPTIONS`) | AP_Arming.cpp:162-167 | "Arming options" (đúng **ARMING_OPTIONS**) | khớp khối AP_Arming | `null` = nguồn | `null` = nguồn | nguồn không có | khớp 3 bit 0..2 | `null` vs `0` (đây là tham số khác) |
| RC_PROTOCOLS (`_PROTOCOLS`) | RC_Channels_VarInfo.h:100-105 | khớp "RC protocols enabled" | khớp | `null` = nguồn | `null` = nguồn | nguồn không có | khớp 18 bit: 0..16,18 | `null` vs **1** |
| ARMING_SKIPCHK (`SKIPCHK`) | AP_Arming.cpp:195-201 | khớp "(bitmask)" | khớp | `null` = nguồn | `null` = nguồn | nguồn không có | khớp bit 1..8,10..19 (không bit 9) | `null` vs **0** |
| LOG_BITMASK | Parameters.cpp:207-212 | khớp | khớp | `null` = nguồn | `null` = nguồn | nguồn không có | khớp bit 0..13,15,17..21 | `null` vs `DEFAULT_LOG_BITMASK` (config.h:547-562) |

**Nhận xét:** phần mô tả/đơn vị/range/values/bitmask **khớp nguồn** ở cả 7 entry (không bịa).
Sai lệch thực sự của B1: (a) `default` luôn `null` dù nguồn luôn khai default — xem §4 E11 và
DB 0/230 row có `default_value`; (b) 2 tên bị bỏ sót; (c) `RC_OPTIONS` trả kèm tham số khác;
(d) 5 excerpt không chứa khối được trích (xem §4 E5, E6, E7; E8 là trường hợp đúng để đối chứng).

---

## 2. B2 — hai con số và tỉ lệ

### 2.1 (a) Số tham số tool BÁO CÁO — đọc trực tiếp `B2_INDEX_STATUS.json`

Payload tại `raw/B2_INDEX_STATUS.json:23`, nguyên văn (decode):

```json
{
  "found": true,
  "counts": {
    "sources": 7,
    "documents": 4908,
    "chunks": 65509
  },
  "index_path": "D:\\Skill_tulan\\ardupilot-research-mcp\\data\\index.sqlite",
  "index_mb": 123.1,
  "last_ingest": "2026-10-25T17:42:44+0700",
  "stale_warning_days": 90,
  "note": "offline mode: no network access at serve time"
}
```

**Trường chính xác:** `"counts"` chỉ có **`sources: 7`, `documents: 4908`, `chunks: 65509`** —
**KHÔNG có trường `params`**. Nghĩa là: **hôm nay tool KHÔNG báo cáo số tham số ở mặt MCP**
(đối chiếu code đọc được trên đĩa: `src/ardupilot_research_mcp/query.py:221-224` chỉ đếm
`sources, documents, chunks`). Con số **230** trong báo cáo cũ lấy từ `db.counts()` (hàm có
`params`), in ra ở `FINAL_REPORT.md:459` — **không phải** từ `index_status`.

Số tham số thực tế mà tool đang phục vụ (bảng `params` của đúng file index mà raw dẫn):
`SELECT COUNT(*) FROM params` trên `data/index.sqlite` = **230** (khớp đúng con số 230 của báo
cáo cũ, và khớp `params: 230` tại `FINAL_REPORT.md:426,459`).

### 2.2 (b) Số khối `@Param:` tìm bằng grep, cùng tag

Regex dùng chung: `^\s*//\s*@Param(\{[^}]*\})?:` (ERE:
`^[[:space:]]*//[[:space:]]*@Param(\{[^}]*\})?:`). Lệnh:

```text
# toàn bộ repo ghim, chỉ file nguồn C/C++
git -C research/cache/git/ardupilot grep -c -E '^[[:space:]]*//[[:space:]]*@Param(\{[^}]*\})?:' \
    fb773567896014da007bca58358704d4a0d8516f -- '*.cpp' '*.h'
# tập con corpus: đúng 550 file .cpp/.h đang có trong data/corpus/ardupilot,
# grep trên blob tại pin của từng file (18 file trong số đó thực sự có @Param)
```

| Phạm vi | Số khối `@Param` | Ghi chú |
|---|---|---|
| **Toàn repo tại pin** (`*.cpp` + `*.h`, 249 file) | **3368** | = 3342 dạng `@Param:` + **26** dạng `@Param{Vai trò}:` |
| **Tập con corpus** (`data/corpus/ardupilot`, 18 file có khối) | **311** | = 309 dạng `@Param:` + **2** dạng `@Param{...}`; 550 file `.cpp/.h` được quét. 18/18 file corpus **byte-equal blob tại pin** (kiểm bằng `scripts/verify_b.py corpushash`) |
| **Bảng `params` của index** | **230** | `SELECT COUNT(*) FROM params` |

Tỉ lệ:

| Tỉ lệ | Giá trị |
|---|---|
| 230 / 3368 (bảng index / toàn repo) | **6,83 %** |
| 230 / 311 (bảng index / tập con corpus) | **73,95 %** |
| 311 / 3368 (corpus / toàn repo) | **9,23 %** |
| 230 / 3342 (chỉ dạng `@Param:` phẳng, toàn repo) | 6,88 % |

### 2.3 Đóng gap 311 → 230 bằng chứng cứ trên đĩa (không đoán)

`scripts/verify_b.py mechanism` tái lập đúng 2 cổng lọc của `research/build_params.py`
(đọc để đối chiếu, không sửa): cổng A = phải thấy dòng khai báo (`AP_GROUPINFO*` hoặc chuỗi
`"<tên>"`) trong 15 dòng kế tiếp và trước dòng code đầu tiên (`build_params.py:84-95`); cổng B =
phải có chunk phủ trọn khối (`build_params.py:116-124`); khoá `UNIQUE(name_raw, vehicle, version)`
(`db.py:84`). Chạy lại trên 18 file corpus:

```text
311 = 2  (@Param{...} — regex của indexer chỉ nhận "@Param:")
    + 25 (khối bị bỏ vì cursor nhảy tới dòng khai báo của khối trước)
    + 52 (cổng A: không thấy khai báo trong 15 dòng / bị dòng code cắt)
    +  0 (cổng B: chunk không phủ khối — 0 trường hợp)
    + 232 khối qua cổng A+B
    = 311
232 khối qua cổng − 2 tên trùng (TYPE, POS_Y) = 230 row  (đúng bằng SELECT COUNT(*) FROM params)
```

Ví dụ cổng A (trích từ chính script, có thể tái chạy): `ArduCopter/mode_flowhold.cpp:12`
`@Param: _XY_P`, `ArduCopter/Parameters.cpp:905` `@Param: ACRO_RP_RATE`,
`libraries/AP_GPS/AP_GPS.cpp:2034` `@Param: _TYPE`.

### 2.4 Giải thích gap một cách trung thực

1. **File ngoài corpus là nhân tố lớn nhất (3057/3368 = 90,8 % số khối nằm ngoài).**
   `sources.yaml` (mục `ardupilot.include`) chỉ lấy: `libraries/AP_HAL*`, `AP_RCProtocol`,
   `RC_Channel`, `AP_Arming`, `AP_Common`, `AP_InertialSensor`, `AP_Param`, `AP_Math`, `AP_GPS`,
   `Tools/**`, `ArduCopter/**`, `docs/**`, `*.md`, `*.txt`. **Không** có `AP_BattMonitor`,
   `AP_SerialManager`, `AP_Vehicle`, `AR_WPNav`, `AC_WPNav`, `ArduPlane/**`, `Rover/**`,
   `ArduSub/**`, `Blimp/**`, `AntennaTracker/**`. Đây chính là lý do gốc của 2 false negative
   có thật: `SERIAL1_PROTOCOL` (khai trong `AP_SerialManager.cpp`) và `BATT_FS_LOW_ACT` (khai
   trong `AP_BattMonitor_Params.cpp`) — file khai báo không được extract vào corpus nên không
   bao giờ vào bảng `params`.
2. **Bộ lọc vehicle không làm mất row nào cho Copter, nhưng chặn mọi vehicle khác.**
   `SELECT vehicle, COUNT(*) FROM params` = `ArduCopter 133` + `shared 97` = **230**; toàn bộ
   bảng nằm trong tập `IN ('ArduCopter','shared')` mà `lookup_param` truy vấn — nên nếu gọi với
   `vehicle="ArduCopter"` (mặc định) thì 100 % row là "nhìn thấy được". Nhưng corpus không có
   `ArduPlane/**`… nên **0 row** cho Plane/Rover/Sub/Tracker; gọi `vehicle="ArduPlane"` sẽ chỉ còn
   97 row `shared`.
3. **`@Param{Plane,Copter,...}` variant:** 26 khối toàn repo, 2 khối trong corpus (đều ở
   `libraries/AP_Arming/AP_Arming.cpp`, dòng 117 `@Param{Plane, Rover}: REQUIRE` và 141
   `@Param{Plane,Rover,Copter,Blimp}: RUDDER`). Regex indexer chỉ khớp `@Param:` phẳng nên **cả 2
   bị bỏ** — đúng như dòng "2" trong phép đóng gap. 24 khối còn lại nằm ngoài corpus.
4. **Dedupe theo suffix:** 230 row = 230 `name_raw` phân biệt, chỉ **220** `name_suffix` phân
   biệt; đúng **10** suffix bị trùng: `ACCOFFS_Y, ACCSCAL_X, ACC_ID, ENABLE, GYROFFS_X, GYR_ID,
   OPTIONS, TMAX, TMIN, USE` (mỗi suffix 2 row). Dedupe theo suffix **không** làm giảm số row
   (bảng giữ đủ 230), nhưng **không thể** dedupe vì đó là các tham số khác nhau. Hệ quả trực
   tiếp: suffix `OPTIONS` có 2 row (`_OPTIONS` của RC_Channel và `OPTIONS` của AP_Arming) nên
   query `RC_OPTIONS` trả về cả hai (xem E4) — 220 < 230 chính là 10 cặp này, **không** dùng để
   giải thích chênh lệch 230 vs 311/3368.
5. **Sai khác 214 / 241 so với 230:** 214 (README.md:13; HANDOFF.md:30,121) và 241
   (HANDOFF.md:40 "241 rows (24 with `@Bitmask`)") **không tái lập được** từ index đang đóng
   băng: bảng hiện có **230 row / 26 row có bitmask**, ngày build duy nhất
   `last_ingest = 2026-10-25T17:42:44+0700` (raw `B2_INDEX_STATUS.json:23`), không có log build
   nào trong raw/artifacts để chứng minh một lần build ra 214 hay 241. ⇒ **KHÔNG XÁC ĐỊNH**
   nguồn gốc 214/241; chỉ **230** là có bằng chứng (DB + FINAL_REPORT.md:426,459).
6. **Kết luận B2:** con số tool phục vụ hôm nay là **230 row** (bảng `params`), tức **6,83 %**
   số khối `@Param` của chính tag (3368) và **73,95 %** số khối trong tập con corpus (311).
   `index_status` **không** công bố con số này nữa.

---

## 3. B3 — input đối nghịch

Payload mỗi case tại `raw/B3_<CASE>.json:27` (tham số tại `:6`).

| Case | input | `found` | `error`/`note` | `params` | `candidates` | Kết luận |
|---|---|---|---|---|---|---|
| `B3_FAKE` | `"ZZ_FAKE_PARAM"` | **false** | `"no parameter matched; nothing was invented"` | `[]` | 10 tên: `_XY_IMAX, _FLOW_MAX, _FILT_HZ, _QUAL_MIN, _BRAKE_RATE, SPD_MS, SPD_HIGH_MS, ALT_LOW_M, BRK_ANGLE, ALT_M` | không bịa description/default/bit; candidates là **nhiễu** (xem dưới) |
| `B3_EMPTY` | `""` | **false** | `"error": "empty parameter name"` | `[]` | `[]` | đúng; không bịa gì |
| `B3_SQLI` | `"FS_THR_ENABLE; DROP TABLE"` | **false** | `"no parameter matched; nothing was invented"` | `[]` | đúng 10 tên như trên | không crash, không bịa; coi như text thường |
| `B3_LONG` | 5000 ký tự `"A"` (đo được `len=5000`) | **false** | `"no parameter matched; nothing was invented"` | `[]` | đúng 10 tên như trên | `duration_ms = 10.1`, không treo; không bịa |

**Không có mô tả/default/bit nào bị bịa:** cả 4 payload chỉ có các khoá
`found, query, vehicle, params, candidates, note` (riêng `B3_EMPTY` có `error`); `params` luôn
`[]`; không có `display_name`, `default`, `bitmask`, `citation`. Đối chiếu SQL trực tiếp:
`B3_SQLI` không làm hỏng DB (câu lệnh dùng tham số binding; raw trả bình thường).

**Candidates là thật hay nhiễu?** — **tham số thật, nhưng là nhiễu vô nghĩa với query**:
`SELECT name_raw FROM params WHERE vehicle IN ('ArduCopter','shared') LIMIT 10` trả **đúng
nguyên danh sách 10 tên trên** (cùng thứ tự), tức candidates = 10 dòng **đầu bảng** chứ không
phải "gần đúng" với input. Các tên này đều là tham số thật tại pin (ví dụ
`ArduCopter/mode_flowhold.cpp:26` `@Param: _XY_IMAX`, `:42` `@Param: _FLOW_MAX`;
`ArduCopter/mode_rtl.cpp:8` `@Param: ALT_M`). Vì vậy câu mô tả tool
(`raw/_meta/tools_list.json:121` "Returns found:false plus **real candidates** when nothing
matches") **không đúng bản chất**: đó là head-of-table, giống nhau cho mọi query không khớp,
không liên quan tới input.

---

## 4. Bằng chứng thô

Mỗi mục: trích **nguyên văn** + vị trí raw/nguồn. Payload raw là chuỗi JSON escape trên một
dòng (xem quy ước đầu file).

**E1 — B2 `index_status`: không có trường `params`.**
`raw/B2_INDEX_STATUS.json:23` (payload): `"counts": { "sources": 7, "documents": 4908, "chunks": 65509 }`.
Không tìm thấy `"params"` trong bất kỳ payload raw nào:
`Select-String docs/blackbox/raw/*.json -Pattern '"params": 2\d\d'` → 0 kết quả.

**E2 — `FS_THR_ENABLE` found:true, default null.**
`raw/B1_FS_THR_ENABLE.json:27`:
`"found": true ... "display_name": "Throttle Failsafe Enable", "description": "The throttle failsafe allows you to configure a software failsafe activated by a setting on the throttle input channel" ... "units": null, "range": null, "default": null, "resolved_by": "exact"`.
Nguồn: `git show fb77356:ArduCopter/Parameters.cpp` **L124-129**:
`// @Param: FS_THR_ENABLE` / `// @DisplayName: Throttle Failsafe Enable` /
`// @Description: The throttle failsafe allows you to configure a software failsafe activated by a setting on the throttle input channel` /
`// @Values:  0:Disabled,1:Enabled always RTL,2:Enabled Continue with Mission in Auto Mode (Removed in 4.0+),3:Enabled always Land,4:Enabled always SmartRTL or RTL,5:Enabled always SmartRTL or Land,6:Enabled Auto DO_LAND_START/DO_RETURN_PATH_START or RTL,7:Enabled always Brake or Land` /
`// @User: Standard` / `GSCALAR(failsafe_throttle,  "FS_THR_ENABLE",   FS_THR_ENABLED_ALWAYS_RTL),`.
Default ở nguồn: `ArduCopter/defines.h:120` `#define FS_THR_ENABLED_ALWAYS_RTL 1`.

**E3 — `FS_THR_VALUE` khớp units/range, thiếu default.**
`raw/B1_FS_THR_VALUE.json:27`: `"units": "PWM", "range": "910 1100", "default": null`.
Nguồn `ArduCopter/Parameters.cpp` **L131-138**: `// @Param: FS_THR_VALUE` … `// @Range: 910 1100`
`// @Units: PWM` `// @Increment: 1` `GSCALAR(failsafe_throttle_value, "FS_THR_VALUE", FS_THR_VALUE_DEFAULT),`;
`ArduCopter/config.h:307` `# define FS_THR_VALUE_DEFAULT 975`.

**E4 — `RC_OPTIONS` trả 2 tham số; tham số thứ 2 là `ARMING_OPTIONS`.**
`raw/B1_RC_OPTIONS.json:27`: `"resolved_by": "suffix"`, `"params": [ {... "name_raw": "_OPTIONS", "name_suffix": "OPTIONS", "display_name": "RC options" ...}, {... "name_raw": "OPTIONS", "display_name": "Arming options", ... "citation": { ... "path": "libraries/AP_Arming/AP_Arming.cpp", "lines": [141, 179] ... } } ], "candidates": ["_OPTIONS","OPTIONS"], "note": "matched by suffix; verify the full name in the citation"`.
Nguồn: `libraries/RC_Channel/RC_Channels_VarInfo.h:92-97` (`@Param: _OPTIONS`, `AP_GROUPINFO("_OPTIONS", 33, ...)`)
+ `ArduCopter/Parameters.cpp:693-694` `AP_SUBGROUPINFO(rc_channels, "RC", 17, ParametersG2, RC_Channels_Copter)` ⇒ `RC` + `_OPTIONS` = **RC_OPTIONS**;
`libraries/AP_Arming/AP_Arming.cpp:162-167` (`@Param: OPTIONS`, `AP_GROUPINFO("OPTIONS", 9, AP_Arming, _arming_options, 0)`)
+ `ArduCopter/Parameters.cpp:238-240` `// @Group: ARMING_` / `GOBJECT(arming, "ARMING_", AP_Arming_Copter)` ⇒ **ARMING_OPTIONS**, không phải RC_OPTIONS.
Báo cáo của chính dự án biết lỗi này và nói "đã fix": `artifacts/FINAL_REPORT.md:79`
`| RC_OPTIONS resolved to AP_Arming's OPTIONS | two params share the suffix | prefix→path ranking (order_suffix_matches) |` — nhưng raw đóng băng vẫn trả tham số đó trong `params`.

**E5 — Excerpt `FS_THR_ENABLE`/`FS_THR_VALUE` là khối của `FS_GCS_ENABLE`.**
`raw/B1_FS_THR_ENABLE.json:27` và `raw/B1_FS_THR_VALUE.json:27`: `"lines": [95,145]`, excerpt bắt đầu
`"    // @Param: FS_GCS_ENABLE\n    // @DisplayName: Ground Station Failsafe Enable\n..."` (độ dài
600) — không chứa `@Param: FS_THR_ENABLE`/`FS_THR_VALUE`. Kiểm bằng script: `excerpt_has_param_line=False`.
Nguồn: `ArduCopter/Parameters.cpp:124` (`@Param: FS_THR_ENABLE`) và `:131` nằm **trong** L95-145,
nhưng excerpt 600 ký tự cắt trước khi tới đó. `FS_GCS_ENABLE` nằm ở L96-101.

**E6 — Excerpt `RC_PROTOCOLS` cũng lấy nhầm khối.**
`raw/B1_RC_PROTOCOLS.json:27`: `"lines": [84,117]`, excerpt bắt đầu `// @Param: _OVERRIDE_TIME`;
`excerpt_has_param_line=False` cho `@Param: _PROTOCOLS`. Nguồn: khối `@Param: _PROTOCOLS` ở
`libraries/RC_Channel/RC_Channels_VarInfo.h:100-105` (trong dải 84-117).

**E7 — Excerpt `ARMING_SKIPCHK` lấy khối `CRSDP_IGN`.**
`raw/B1_ARMING_SKIPCHK.json:27`: `"lines": [178,205]`, excerpt bắt đầu
`// @Param: CRSDP_IGN`; `excerpt_has_param_line=False`. Nguồn: khối `@Param: SKIPCHK` ở
`libraries/AP_Arming/AP_Arming.cpp:195-201` (trong dải 178-205).

**E8 — Excerpt `LOG_BITMASK` thì đúng (đối chứng).**
`raw/B1_LOG_BITMASK.json:27`: `"lines": [199,232]`, `excerpt_has_param_line=True`; excerpt chứa
`// @Param: LOG_BITMASK`. Nguồn khối: `ArduCopter/Parameters.cpp:207-212`.

**E9 — `SERIAL1_PROTOCOL` bị bỏ sót.**
`raw/B1_SERIAL1_PROTOCOL.json:27`: `"found": false, "params": [], "candidates": ["_XY_IMAX", …], "note": "no parameter matched; nothing was invented"`.
Nguồn có thật: `git show fb77356:libraries/AP_SerialManager/AP_SerialManager.cpp` **L183-191**:
`#if HAL_HAVE_SERIAL1_PARAMS` / `// @Param: 1_PROTOCOL` / `// @DisplayName: Telem1 protocol selection` /
`// @Description: Control what protocol to use on the Telem1 port...` / `// @Values: -1:None, 1:MAVLink1, 2:MAVLink2, ... 50: IOMCU` /
`// @User: Standard` / `// @RebootRequired: True` / `AP_GROUPINFO("1_PROTOCOL", 1, AP_SerialManager, state[1].protocol, DEFAULT_SERIAL1_PROTOCOL),`.
Prefix: `libraries/AP_Vehicle/AP_Vehicle.cpp:283-287` `// @Group: SERIAL` + `AP_SUBGROUPINFO(serial_manager, "SERIAL", 31, AP_Vehicle, AP_SerialManager)` ⇒ **SERIAL1_PROTOCOL**.
Tên đầy đủ còn xuất hiện trong chính repo tại pin: `Tools/autotest/default_params/vee-gull_005.param:518` `SERIAL1_PROTOCOL,1`;
`libraries/AP_DDS/README.md:79` `| SERIAL1_PROTOCOL | Set this to 45 ...`;
`libraries/AP_DroneCAN/AP_DroneCAN.cpp:214` `// @CopyFieldsFrom: SERIAL1_PROTOCOL`.
Default: `AP_SerialManager.cpp:47-48` `#define DEFAULT_SERIAL1_PROTOCOL SerialProtocol_MAVLink2`;
`libraries/AP_SerialManager/AP_SerialManager.h:41` `SerialProtocol_MAVLink2 = 2`.

**E10 — `BATT_FS_LOW_ACT` bị bỏ sót.**
`raw/B1_BATT_FS_LOW_ACT.json:27`: `"found": false, "params": [], "candidates": [...], "note": "no parameter matched; nothing was invented"`.
Nguồn có thật: `libraries/AP_BattMonitor/AP_BattMonitor_Params.cpp` **L143-153**:
`// @Param: FS_LOW_ACT` / `// @DisplayName: Low battery failsafe action` /
`// @Description: What action the vehicle should perform if it hits a low battery failsafe` /
`// @Values{Copter}: 0:Warn only,1:Land,2:RTL,3:SmartRTL or RTL,4:SmartRTL or Land,5:Terminate,6:Auto DO_LAND_START/DO_RETURN_PATH_START or RTL,7:Brake or Land` / `// @User: Standard` /
`AP_GROUPINFO("FS_LOW_ACT", 16, AP_BattMonitor_Params, _failsafe_low_action, 0),`.
Ghép prefix: `ArduCopter/Parameters.cpp:401-403` `// @Group: BATT` + `GOBJECT(battery, "BATT", AP_BattMonitor)`;
`libraries/AP_BattMonitor/AP_BattMonitor.cpp:55` `AP_SUBGROUPINFO(_params[0], "_", 23, AP_BattMonitor, AP_BattMonitor_Params)`
⇒ `BATT` + `_` + `FS_LOW_ACT` = **BATT_FS_LOW_ACT**. Tên đầy đủ có trong repo tại pin:
`Tools/Frame_params/3DR_Iris+.param:27` `BATT_FS_LOW_ACT,2`; `Tools/autotest/arducopter.py:1415` `'BATT_FS_LOW_ACT': 0`.

**E11 — Default bị mất có hệ thống ở mọi row.**
`data/index.sqlite`: `SELECT COUNT(*) FROM params WHERE default_value IS NOT NULL` = **0** trên
230 row (script `verify_b.py db`). Nguyên nhân đọc được: `research/build_params.py:97-102` lấy
default bằng `decl.rsplit(",", 1)` — với dòng khai báo kết thúc `),` (đa số), phần sau dấu phẩy
cuối là rỗng nên `default = None`. Raw phản ánh đúng: `"default": null` ở mọi entry found.

**E12 — `RC_OPTIONS` bitmask khớp nguồn.**
`raw/B1_RC_OPTIONS.json:27` entry 1 có `"bitmask"` bit 0..13, tên ví dụ
`{"bit": 5, "name": "Arming check throttle for 0 input"}`, `{"bit": 13, "name": "Use 420kbaud for ELRS protocol"}`.
Nguồn `libraries/RC_Channel/RC_Channels_VarInfo.h:96`:
`// @Bitmask: 0:Ignore RC Receiver, 1:Ignore MAVLink Overrides, 2:Ignore Receiver Failsafe bit but allow other RC failsafes if setup, 3:FPort Pad, 4:Log RC input bytes, 5:Arming check throttle for 0 input, 6:Skip the arming check for neutral Roll/Pitch/Yaw sticks, 7:Allow Switch reverse, 8:Use passthrough for CRSF telemetry, 9:Suppress CRSF mode/rate message for ELRS systems,10:Enable multiple receiver support, 11:Use Link Quality for RSSI with CRSF, 12:Annotate CRSF flight mode with * on disarm, 13: Use 420kbaud for ELRS protocol`.

**E13 — `RC_PROTOCOLS`/`ARMING_SKIPCHK`/`LOG_BITMASK` bitmask khớp nguồn.**
`raw/B1_RC_PROTOCOLS.json:27` bit `0,1,...,16,18` vs nguồn `RC_Channels_VarInfo.h:104`
(`0:All ... 16:MAVRadio,18:SITL UDP`);
`raw/B1_ARMING_SKIPCHK.json:27` bit `1..8,10..19` vs nguồn `AP_Arming.cpp:198`
(`1:Barometer,...,8:Battery Level,10:Logging Available,...,19:FFT`);
`raw/B1_LOG_BITMASK.json:27` bit `0..13,15,17..21` vs nguồn `ArduCopter/Parameters.cpp:210`
(`0:Fast Attitude,...,13:Compass,15:Camera,17:Motors,18:Fast IMU,19:Raw IMU,20:Video Stabilization,21:Fast harmonic notch logging`).

**E14 — `ARMING_CHECK` không tồn tại ở tag.**
`raw/B1_ARMING_CHECK.json:27`: `"found": false ... "note": "no parameter matched; nothing was invented"`.
Nguồn: `ArduCopter/ReleaseNotes.txt:651-654` (mục "5) Parameter scaling and/or renaming related changes"):
`- ARMING_CHECK replaced with ARMING_SKIPCHK (@tpwrules, PR:31568)`;
`libraries/AP_Arming/AP_Arming.cpp:160` `// index 8 was CHECK stored as AP_Int32, became SKIPCHK`;
`:228` `// PARAM_CONVERSION - 4.7 CHECK -> SKIPCHK`.
Grep `@Param.*ARMING_CHECK` trên toàn repo tại pin → **0 kết quả**.

**E15 — `WPNAV_SPEED` không tồn tại ở tag (đã thành `WP_SPD`).**
`raw/B1_WPNAV_SPEED.json:27`: `"found": false ...`.
Nguồn: `libraries/AC_WPNav/AC_WPNav.cpp:49-56` `// @Param: SPD` … `AP_GROUPINFO("SPD", 14, AC_WPNav, _wp_speed_ms, WP_SPD_DEFAULT),`;
`:141` `{ 55, 0, AP_PARAM_FLOAT, "WP_SPD" }, // old WPNAV_SPEED at index 0`;
prefix `ArduCopter/Parameters.cpp:369` `GOBJECTPTR(wp_nav, "WP_", AC_WPNav)`.
`grep -n '@Param.*WPNAV_SPEED'` tại pin → 0 (chỉ còn trong `ArduCopter/ReleaseNotes.txt`).

**E16 — Candidates của mọi query không khớp là head-of-table.**
`SELECT name_raw FROM params WHERE vehicle IN ('ArduCopter','shared') LIMIT 10` →
`_XY_IMAX, _FLOW_MAX, _FILT_HZ, _QUAL_MIN, _BRAKE_RATE, SPD_MS, SPD_HIGH_MS, ALT_LOW_M, BRK_ANGLE, ALT_M`
— trùng khít `"candidates"` tại `raw/B3_FAKE.json:27`, `raw/B3_SQLI.json:27`, `raw/B3_LONG.json:27`,
`raw/B1_ARMING_CHECK.json:27`, `raw/B1_SERIAL1_PROTOCOL.json:27`, `raw/B1_BATT_FS_LOW_ACT.json:27`,
`raw/B1_WPNAV_SPEED.json:27`.
Chúng là tham số thật: `ArduCopter/mode_flowhold.cpp:26` `@Param: _XY_IMAX`, `:42` `@Param: _FLOW_MAX`,
`:49` `@Param: _FILT_HZ`, `:57` `@Param: _QUAL_MIN`, `:66` `@Param: _BRAKE_RATE`;
`ArduCopter/mode_land.cpp:6,24` `@Param: SPD_MS`, `@Param: ALT_LOW_M`; `ArduCopter/mode_poshold.cpp:35` `@Param: BRK_ANGLE`;
`ArduCopter/mode_rtl.cpp:8` `@Param: ALT_M`.

**E17 — B3 empty/SQLI/5000 ký tự không bịa gì.**
`raw/B3_EMPTY.json:27`: `{"found": false, "error": "empty parameter name", "candidates": []}`.
`raw/B3_SQLI.json:27`: `{"found": false, "query": "FS_THR_ENABLE; DROP TABLE", ... "params": [], "candidates": [...], "note": "no parameter matched; nothing was invented"}`.
`raw/B3_LONG.json:27`: `{"found": false, "query": "AAAA…(5000 ký tự)", ... "params": [], "candidates": [...], "note": "no parameter matched; nothing was invented"}`, `duration_ms = 10.1` (trường `duration_ms` trong file raw).
Không có khoá `display_name`/`default`/`bitmask`/`citation` trong cả 4 payload B3.

---

## 5. Mọi chỗ tool khẳng định điều nguồn ghim không ủng hộ

1. **`RC_OPTIONS` được "khớp" với `OPTIONS` của AP_Arming** — đó là **`ARMING_OPTIONS`**, không
   phải `RC_OPTIONS` (`raw/B1_RC_OPTIONS.json:27` entry 2; nguồn `AP_Arming.cpp:162-167` +
   `ArduCopter/Parameters.cpp:238-240`). Dự án tự ghi nhận lỗi này và nói đã xếp hạng lại
   (`artifacts/FINAL_REPORT.md:79`) nhưng output đóng băng vẫn trả tham số sai trong `params`.
2. **`"default": null` cho mọi tham số** trong khi nguồn luôn khai default:
   `FS_THR_ENABLE`→1, `FS_THR_VALUE`→975, `RC_OPTIONS`→32, `RC_PROTOCOLS`→1,
   `ARMING_SKIPCHK`→0, `LOG_BITMASK`→macro (E2/E3/E11). Bảng index 0/230 row có `default_value`.
3. **`found:false` cho `SERIAL1_PROTOCOL` và `BATT_FS_LOW_ACT`** — hai tham số **có thật** ở tag
   (E9/E10); câu `"no parameter matched; nothing was invented"` đúng về "không bịa", nhưng hệ quả
   là tool phủ nhận sự tồn tại của tham số.
4. **Mô tả tool "found:false plus real candidates"** (`raw/_meta/tools_list.json:121`): candidates
   không phải "candidates" mà là 10 dòng đầu bảng `params`, giống nhau cho mọi query không khớp
   (E16) — không liên quan tới input.
5. **Excerpt của citation không chứa khối được trích** cho `FS_THR_ENABLE`, `FS_THR_VALUE`,
   `RC_PROTOCOLS`, `ARMING_SKIPCHK`, và entry `OPTIONS` (E5/E6/E7). URL/line range thì đúng
   (khối nằm trong dải dòng), nhưng phần "trích dẫn nguyên văn" lại là khối của tham số khác —
   người đọc không thể đối chiếu mô tả từ excerpt.
6. **Tài liệu dự án tự mâu thuẫn về số tham số**: `README.md:13` "214 params";
   `HANDOFF.md:30` "214 params (26 with @Bitmask)"; `HANDOFF.md:40` "241 rows (24 with @Bitmask)";
   `HANDOFF.md:121` "214 rows"; `FINAL_REPORT.md:426,459` "params": 230. Bảng thật hôm nay: 230
   row / 26 bitmask. Chỉ 230 có bằng chứng; 214/241 không tái lập được (§2.4.5).
7. **`index_status` từng được báo cáo là trả `params`** (`FINAL_REPORT.md:426,459`) nhưng raw
   `B2_INDEX_STATUS.json:23` không có trường này, và code hiện tại `query.py:221-224` cũng không
   đếm `params` — con số 230 lấy từ `db.counts()`, không phải từ tool call.
8. **`ARMING_SKIPCHK` trả `name_raw: "SKIPCHK"`** mà không nêu tên đầy đủ
   (`raw/B1_ARMING_SKIPCHK.json:27`); trường `name_note` chỉ được thêm cho tên bắt đầu bằng `_`
   (`src/.../lookup_param.py:50-52`). Không phải khẳng định sai, nhưng người dùng không thấy
   tên tham số thật cần gõ (`ARMING_SKIPCHK`). Tương tự `RC_PROTOCOLS`→`_PROTOCOLS`,
   `RC_OPTIONS`→`_OPTIONS` (các entry này **có** `name_note`).

---

## 6. Không xác định được (KHÔNG XÁC ĐỊNH)

1. **Nguồn gốc con số 214 và 241** trong README/HANDOFF: không có log build nào trong
   `docs/blackbox/raw/_meta/` hay `artifacts/` ghi lại một lần build tạo 214/241 row; index đóng
   băng chỉ có một `last_ingest` và 230 row. Không thể chứng minh chúng đến từ bản corpus/phiên
   bản parser nào ⇒ **KHÔNG XÁC ĐỊNH**.
2. **Thời điểm/phiên bản `research/build_params.py` đã dùng để build index**: file hiện tại có
   logic trích default (`:97-102`) nhưng DB có 0/230 default — chứng tỏ bản chạy lúc build khác
   bản đang có trên đĩa; không có log/commit để xác định ⇒ **KHÔNG XÁC ĐỊNH** (chỉ khẳng định
   được *triệu chứng*: default trống toàn bộ).
3. **Việc `lookup_param` có "cố ý" coi `OPTIONS` của AP_Arming là cùng họ hay không**: output có
   `note` cảnh báo suffix và thứ hạng path-first, nên không thể kết luận đó là "khẳng định sai
   chủ ý" hay "candidate có cảnh báo" — tôi ghi nhận là **false positive về mặt precision**
   (trả tham số khác trong `params`), không quy kết ý đồ.

---

## 7. Cách tái lập

```powershell
$env:PYTHONUTF8='1'
python scripts/verify_b.py             # bảng B1 từ raw
python scripts/verify_b.py table       # trường chi tiết từng entry
python scripts/verify_b.py compare     # so từng trường với khối @Param tại pin
python scripts/verify_b.py count       # 3368 (whole) vs 311 (corpus)
python scripts/verify_b.py variants    # 3342/26 và 309/2, dedupe tên
python scripts/verify_b.py mechanism   # đóng gap 311 -> 230
python scripts/verify_b.py db          # 230 row, 0 default, vehicle, candidates head
python scripts/verify_b.py gap         # block/file vs row/file
python scripts/verify_b.py corpushash  # 18/18 file corpus == blob tại pin
```
