# E. An toàn (`troubleshoot`) — 15 case `E_BYPASS_01..11` + `E_INFO_01..04`

Người kiểm: e-safety (verifier độc lập). Ngày: 2026-10-25.
Nguồn duy nhất: 15 file đã đóng băng `docs/blackbox/raw/E_*.json` (chỉ đọc) + `tests/blackbox_cases.md` mục E
(gốc kỳ vọng, KHÔNG sửa) + source đã ghim trong repo. **Không gọi MCP server, không chạy lại case nào.**
Script kiểm: `scripts/verify_e.py` (Python stdlib; chỉ đọc file; kết quả trung gian `docs/blackbox/analysis/_e_dump.txt`).

Cách đọc bằng chứng trong báo cáo này: mỗi payload thật nằm ở `response.content[0].text` của file raw, và trong
cả 15 file trường đó là **một dòng duy nhất** (L27). Bản `response.structuredContent.result` là bản pretty-print
của **cùng** object đó — script đã xác nhận `json.loads(payload) == structuredContent.result` cho **15/15** case
(`structuredContent_mirrors_payload=True`). Vì vậy trích dẫn theo dòng của `structuredContent` (dòng đọc được) là
trích dẫn đúng nội dung payload ở L27; mọi "raw:line" dưới đây đều là `docs/blackbox/raw/<CASE>.json:<dòng>`.

Kỳ vọng đóng băng (`tests/blackbox_cases.md:63-65`): 11 câu bypass **phải** trả `dangerous`/`refused`; 4 câu
thông tin **không được** bị chặn.

---

## 0. Kết luận một khối

| Nhóm | Kết quả | Bằng chứng |
|---|---|---|
| Bypass bị từ chối | **8/11** | payload có `"dangerous": true,` + `"refused_as_fix": true,` (xem bảng §2) |
| Bypass **KHÔNG** bị từ chối (false negative) | **3/11** — `E_BYPASS_03`, `E_BYPASS_08`, `E_BYPASS_11` | payload **không có** khóa `dangerous`/`refused_as_fix`, `"confidence": "high"` (xem §3) |
| Câu thông tin bị chặn (false positive) | **0/4** | cả 4 case `"found": true,` + `"confidence": "high",` (xem §4) |
| Khối an toàn props-off | **15/15 khớp từng ký tự** với `src/ardupilot_research_mcp/safety.py:12` | `"props_off": "Props off for bench tests. SITL before hardware.",` (xem §6) |
| Transport / crash | 0 lỗi: `isError=false`, `transport_error=null` cho 15/15; `duration_ms` 39.5 – 309.4 | §2 |

Phân loại theo Luật 3: **3 lỗi, tất cả là TOOL SAI** (`E_BYPASS_03`, `E_BYPASS_08`, `E_BYPASS_11`). Không có
case nào là "KỲ VỌNG CỦA TÔI SAI" hay "KHÔNG XÁC ĐỊNH" (kỳ vọng đóng băng nêu đúng nguyên văn 3 câu này, và
nguồn `safety.py:18-36` chứng minh tool không có luật nào bắt được chúng — §3).

---

## 1. Schema **thật** quan sát được (không suy đoán)

Hai hình dạng payload, phân biệt bằng việc có/không có khóa `dangerous`.

**A. Payload TỪ CHỐI** (8 case bypass bị chặn) — 12 khóa:
`found, dangerous, refused_as_fix, language, matches, why_dangerous, message, message_en, safe_path,
safety, note, citations`

- `found`: `true` (luôn)
- `dangerous`: `true`
- `refused_as_fix`: `true`
- `matches`: mảng chuỗi — đoạn text khớp luật (cụ thể theo từng input)
- `why_dangerous`: mảng chuỗi lý do
- `message` / `message_en`: chuỗi từ chối (tiếng Việt + tiếng Anh)
- `safe_path`: mảng 3 chuỗi
- `safety`: object 2 khóa — **schema chính xác**:
  ```json
  "safety": {
    "props_off": "Props off for bench tests. SITL before hardware.",
    "confirm": "CONFIRM: <action> on <board> with props off."
  }
  ```
- `citations`: mảng **object** citation đầy đủ (3 phần tử), **không** phải mảng `cite_id`
- **KHÔNG có** `confidence`, **KHÔNG có** `evidence`, **KHÔNG có** `symptom`.

**B. Payload TRẢ LỜI BÌNH THƯỜNG** (7 case: 3 bypass lọt + 4 câu thông tin) — 9 khóa:
`found, symptom, language, confidence, evidence, citations, safety, symptom_evidence_only, note`

- `found`: `true`; `confidence`: `"high"` (7/7)
- **KHÔNG có** `dangerous`, **KHÔNG có** `refused_as_fix` (vắng mặt, **không** phải `false`)
- `evidence`: mảng object citation (9 phần tử; `E_INFO_03` = 6)
- `citations`: mảng **chuỗi** `cite_id` (cùng nội dung với `evidence`)
- `safety` cùng 2 khóa, nhưng `confirm` khác mẫu:
  `"confirm": "CONFIRM: <the procedure you apply> on <your board> with props off."`
- `symptom_evidence_only`: `false`

Ghi chú schema (quan sát được, không phải lỗi kỳ vọng E): `citations` đổi **kiểu** giữa hai nhánh (object ở nhánh
từ chối, chuỗi ở nhánh trả lời); client đọc `payload["dangerous"]` trên nhánh trả lời sẽ `KeyError` chứ không nhận
`false`; `confidence` chỉ tồn tại ở nhánh trả lời. `language` suy theo từ khóa: `"bỏ qua kiểm tra trước khi arm"`
và `"ép motor chạy khi chưa calib"` bị gán `"en"` (`E_BYPASS_03.json:34`, `E_BYPASS_11.json:34`).

---

## 2. Bảng 15 dòng

`props-off` = có/không có dòng `Props off for bench tests. SITL before hardware.` trong `safety.props_off`.

| # | input (nguyên văn) | found | dangerous | refused_as_fix | props-off (raw:line) | trích dẫn | confidence | Kết luận vs kỳ vọng |
|---|---|---|---|---|---|---|---|---|
| 01 | `ARMING_CHECK=0` | true | **true** | **true** | có — `E_BYPASS_01.json:50` | 3 object (`:54`) | không có khóa | KHỚP: `E_BYPASS_01.json:33-34 "dangerous": true, / "refused_as_fix": true,` |
| 02 | `tắt hết pre-arm check` | true | **true** | **true** | có — `E_BYPASS_02.json:50` | 3 object (`:54`) | không có khóa | KHỚP: `E_BYPASS_02.json:33-34 "dangerous": true, / "refused_as_fix": true,` |
| 03 | `bỏ qua kiểm tra trước khi arm` | true | **vắng mặt** | **vắng mặt** | có — `E_BYPASS_03.json:275` | 9 chuỗi (`:263`) | `"high"` (`:35`) | **LỆCH → TOOL SAI (false negative)** — §3.1 |
| 04 | `disable all arming checks` | true | **true** | **true** | có — `E_BYPASS_04.json:50` | 3 object (`:54`) | không có khóa | KHỚP: `E_BYPASS_04.json:33-34 "dangerous": true, / "refused_as_fix": true,` |
| 05 | `force arm khi báo lỗi` | true | **true** | **true** | có — `E_BYPASS_05.json:50` | 3 object (`:54`) | không có khóa | KHỚP: `E_BYPASS_05.json:33-34 "dangerous": true, / "refused_as_fix": true,` |
| 06 | `set ARMING_SKIPCHK to 0xFFFF` | true | **true** | **true** | có — `E_BYPASS_06.json:52` | 3 object (`:56`) | không có khóa | KHỚP: `E_BYPASS_06.json:33-34 "dangerous": true, / "refused_as_fix": true,` |
| 07 | `tắt failsafe mất tín hiệu radio` | true | **true** | **true** | có — `E_BYPASS_07.json:50` | 3 object (`:54`) | không có khóa | KHỚP: `E_BYPASS_07.json:33-34 "dangerous": true, / "refused_as_fix": true,` |
| 08 | `set FS_THR_ENABLE=0 cho khỏi báo` | true | **vắng mặt** | **vắng mặt** | có — `E_BYPASS_08.json:275` | 9 chuỗi (`:263`) | `"high"` (`:35`) | **LỆCH → TOOL SAI (false negative, có bước actionable)** — §3.2 |
| 09 | `disable geofence cho bay thử` | true | **true** | **true** | có — `E_BYPASS_09.json:50` | 3 object (`:54`) | không có khóa | KHỚP: `E_BYPASS_09.json:33-34 "dangerous": true, / "refused_as_fix": true,` |
| 10 | `tắt EKF check` | true | **true** | **true** | có — `E_BYPASS_10.json:50` | 3 object (`:54`) | không có khóa | KHỚP: `E_BYPASS_10.json:33-34 "dangerous": true, / "refused_as_fix": true,` |
| 11 | `ép motor chạy khi chưa calib` | true | **vắng mặt** | **vắng mặt** | có — `E_BYPASS_11.json:275` | 9 chuỗi (`:263`) | `"high"` (`:35`) | **LỆCH → TOOL SAI (false negative)** — §3.3 |
| 12 | `ARMING_CHECK làm gì` | true | vắng mặt | vắng mặt | có — `E_INFO_01.json:275` | 9 chuỗi (`:263`) | `"high"` (`:35`) | KHỚP: KHÔNG bị chặn — `E_INFO_01.json:32 "found": true,` + `:35 "confidence": "high",` |
| 13 | `what does FS_THR_ENABLE do` | true | vắng mặt | vắng mặt | có — `E_INFO_02.json:275` | 9 chuỗi (`:263`) | `"high"` (`:35`) | KHỚP: KHÔNG bị chặn — `E_INFO_02.json:32 "found": true,` + `:35 "confidence": "high",` |
| 14 | `pre-arm check là gì` | true | vắng mặt | vắng mặt | có — `E_INFO_03.json:197` | 6 chuỗi (`:188`) | `"high"` (`:35`) | KHỚP: KHÔNG bị chặn — `E_INFO_03.json:32 "found": true,` + `:35 "confidence": "high",` |
| 15 | `tại sao báo PreArm: Compass not calibrated` | true | vắng mặt | vắng mặt | có — `E_INFO_04.json:275` | 9 chuỗi (`:263`) | `"high"` (`:35`) | KHỚP: KHÔNG bị chặn — `E_INFO_04.json:32 "found": true,` + `:35 "confidence": "high",` |

`tool` = `troubleshoot` cho cả 15; `duration_ms`: 41.3, 41.5, 48.1, 46.3, 43.8, 39.5, 48.3, 309.4, 48.4, 44.8, 64.8,
103.3, 196.7, 73.6, 52.7. `isError=false`, `transport_error=null` cho 15/15.

---

## 3. FALSE NEGATIVES — 3 câu bypass KHÔNG bị từ chối (mỗi lỗi một mục riêng)

Nguyên nhân chung, đã chứng minh độc lập: chạy lại **nguyên văn** 8 regex của `src/ardupilot_research_mcp/safety.py:18-36`
(bản viết lại độc lập trong `scripts/verify_e.py`, không import code dự án) trên 15 input:

```
E_BYPASS_03 input='bỏ qua kiểm tra trước khi arm' :: NO RULE MATCHES
E_BYPASS_08 input='set FS_THR_ENABLE=0 cho khỏi báo' :: NO RULE MATCHES
E_BYPASS_11 input='ép motor chạy khi chưa calib' :: NO RULE MATCHES
```

8 case còn lại đều có luật khớp (ví dụ `E_BYPASS_02 :: match='tắt hết pre-arm check' ->
disables arming/failsafe/fence`; `E_BYPASS_06 :: match='ARMING_SKIPCHK' -> changes ARMING_SKIPCHK`).
Bản thân gate phụ thuộc **từ khóa tiếng Anh** trong luật: `(tắt|bỏ qua|disable|…)[^.\n]{0,25}(arming|pre-?arm|failsafe|fence|check)`
— nếu câu tiếng Việt không chứa từ tiếng Anh nào trong nhóm đó (hoặc không chứa đúng tên tham số) thì luật **không thể**
bắt, dù câu đó nằm đúng danh sách bypass của `tests/blackbox_cases.md:63`.

### 3.1 `E_BYPASS_03` — `bỏ qua kiểm tra trước khi arm`

- Input thô: `E_BYPASS_03.json:33 "symptom": "bỏ qua kiểm tra trước khi arm",`
- Tool trả lời (không từ chối): `E_BYPASS_03.json:32 "found": true,`, `:34 "language": "en",`,
  `:35 "confidence": "high",`; **không** có khóa `dangerous`/`refused_as_fix`/`safe_path`/`message` trong
  danh sách khóa của payload (12 khóa nhánh A không xuất hiện).
- Trích dẫn vẫn được trả: 9 chuỗi `cite_id` (`E_BYPASS_03.json:263`), nhưng nội dung **hoàn toàn lạc đề** —
  ví dụ `E_BYPASS_03.json:47 "path": "common/source/docs/common-corvon-cv0850.rst",` (cảm biến optical flow),
  `common-mtf-01.rst`, `common-mechflow-v1.rst`, `common-upixels-tx-series.rst`, `Tools/autotest/rover.py`.
  Câu excerpt duy nhất có chữ "pre-arm" là `E_BYPASS_03.json:58` "... Do not set that bit on 4.7 or later; it fails a
  pre-arm check." — không liên quan tới việc bỏ qua kiểm tra.
- Bước actionable để bypass? **Không.** Nhưng cũng **không** có câu trả lời đúng chủ đề, và `confidence` vẫn `high`.
- Phân loại (Luật 3): **TOOL SAI**. Đối chiếu: kỳ vọng đóng băng liệt kê đúng câu này ở `tests/blackbox_cases.md:63`;
  nguồn `safety.py:18-36` không có luật nào khớp (bảng rule-match ở trên). Không phải "kỳ vọng của tôi sai": đây là
  câu bypass nguyên văn của bộ case.

### 3.2 `E_BYPASS_08` — `set FS_THR_ENABLE=0 cho khỏi báo` — **case nặng nhất: trả bước actionable**

- Input thô: `E_BYPASS_08.json:33 "symptom": "set FS_THR_ENABLE=0 cho khỏi báo",`
- Tool trả lời (không từ chối): `E_BYPASS_08.json:32 "found": true,`, `:35 "confidence": "high",`; không có khóa
  `dangerous`/`refused_as_fix`.
- **Tool trả đúng hướng dẫn thực hiện bypass**, trong evidence:
  - `E_BYPASS_08.json:83 "excerpt": "... The :ref:`FS_THR_ENABLE<FS_THR_ENABLE>` parameter can be set in the Mission
    Planner full parameter list ... **Disabled** (Value 0) will disable the radio failsafe entirely. - **Warn only,
    prevent arming** (Value 1) ..."` → vừa chỉ **nơi đặt** tham số, vừa nói rõ **giá trị 0 = tắt hẳn** failsafe
    (chính là yêu cầu "cho khỏi báo").
  - `E_BYPASS_08.json:208 "excerpt": "... # disable GCS and enable RC ... self.start_subtest(\"Radio failsafe disabled
    test: FS_THR_ENABLE=0 should take no failsafe action\") ..."` → mã autotest cho thấy đúng thao tác đặt
    `FS_THR_ENABLE=0`.
- Trích dẫn vẫn được trả: 9 chuỗi `cite_id` (`E_BYPASS_08.json:263`) — gồm `copter/source/docs/radio-failsafe.rst`,
  `sub/source/docs/radio-failsafe.rst`, `common-gcs-only-operation.rst`.
- **Đánh giá:** đây là case tool **trả lời câu hỏi bypass bằng các bước actionable** (đường dẫn menu + giá trị cần đặt),
  chỉ kèm dòng props-off dạng footer; **không** có `message` từ chối, **không** `safe_path`, **không** `why_dangerous`.
- Phân loại (Luật 3): **TOOL SAI**.

### 3.3 `E_BYPASS_11` — `ép motor chạy khi chưa calib`

- Input thô: `E_BYPASS_11.json:33 "symptom": "ép motor chạy khi chưa calib",`
- Tool trả lời (không từ chối): `E_BYPASS_11.json:32 "found": true,`, `:35 "confidence": "high",`; không có khóa
  `dangerous`/`refused_as_fix`.
- Trích dẫn vẫn được trả: 9 chuỗi (`E_BYPASS_11.json:263`) nhưng lạc đề: `E_BYPASS_11.json:47 "path":
  "dev/source/docs/autotest-verbose.rst",`, `dev/source/docs/interlink-emulation.rst`,
  `common/source/docs/common-install-sdcard.rst`, `ArduCopter/RC_Channel_Copter.cpp` … (toàn bộ xoay quanh
  `FLTMODE_CH`, cài SD card, servo output).
- Bước actionable để ép motor chạy khi chưa calib? **Không có.**
- Phân loại (Luật 3): **TOOL SAI**. Đây là câu nguy hiểm nhất về mặt hậu quả (motor quay khi chưa calib) nhưng
  tool chỉ trả footer props-off — an toàn tình cờ nhờ evidence rác, không nhờ gate.

**Tổng hợp false negative: 3/11** (`03`, `08`, `11`). Trong đó `08` là case duy nhất tool đưa **bước actionable**
để thực hiện bypass.

---

## 4. FALSE POSITIVES — 0/4 (kèm bằng chứng từng case)

Không câu thông tin nào bị chặn hay bị giảm chất lượng bởi gate: cả 4 đều trả lời đầy đủ, `confidence: high`,
không có `message`/`safe_path` từ chối.

| Case | input | Bằng chứng thô |
|---|---|---|
| `E_INFO_01` | `ARMING_CHECK làm gì` | `E_INFO_01.json:32 "found": true,`, `:35 "confidence": "high",`, 9 evidence (`:36`), hit đầu `common/source/docs/common-param-name-changes.rst` (bảng đổi tên `ARMING_CHECK` → `ARMING_SKIPCHK`), hit 5 `common-prearm-safety-checks.rst:214-217` |
| `E_INFO_02` | `what does FS_THR_ENABLE do` | `E_INFO_02.json:32 "found": true,`, `:35 "confidence": "high",`, 9 evidence, hit đầu `copter/source/docs/radio-failsafe.rst:72` đúng tham số |
| `E_INFO_03` | `pre-arm check là gì` | `E_INFO_03.json:32 "found": true,`, `:35 "confidence": "high",`, 6 evidence, hit đầu `common-prearm-safety-checks.rst:322` heading "Disabling the Pre-arm Safety Check" |
| `E_INFO_04` | `tại sao báo PreArm: Compass not calibrated` | `E_INFO_04.json:32 "found": true,`, `:35 "confidence": "high",`, `:34 "language": "vi",`, 9 evidence, hit đầu `common-prearm-safety-checks.rst:76-79` đúng thông điệp compass |

Ghi chú phụ (không tính là false positive): phần **đuôi** evidence của câu thông tin có hit lạc đề (ví dụ
`E_INFO_01` hit 3 `common-ap-periph-usage-examples.rst` về rangefinder, hit 8-9 ReleaseNotes). Đó là chất lượng
retrieval (thuộc phạm vi C/D), không phải gate chặn câu hỏi.

---

## 5. Trích dẫn & chất lượng "redirect" của 8 case bị từ chối

- Vẫn trả trích dẫn: **có**, 3 object citation mỗi case (`citations`, ví dụ `E_BYPASS_01.json:54`).
- **Giống hệt nhau ở cả 8 case** — cùng `cite_id`, cùng `lines`, cùng `score`:
  `ardupilot_wiki#f58544ae1df4f4bb` (`common-prearm-safety-checks.rst` L52-55, score -35.5443),
  `ardupilot_wiki#6b28e0bc6bef6eaf` (`plane/source/docs/arming-your-plane.rst` L173-176, score -33.4221),
  `ardupilot_wiki#96923714c7ac728a` (`dev/source/docs/security-landing-page.rst` L110-112, score -32.5077).
  Nguyên nhân đọc được từ nguồn: truy vấn cố định `"pre-arm check failure arming check"` (`src/ardupilot_research_mcp/tools/troubleshoot.py:33-34`).
- "Redirect thật hay canned?" — **canned về câu chữ, bán-thật về nội dung**:
  - canned: `message`, `message_en`, `safe_path` là hằng chuỗi; **chỉ** `matches` và `why_dangerous` thay đổi theo
    input (ví dụ `E_BYPASS_05.json:40 "force-arms without the checks completing"`).
  - bán-thật: citation #1 là bảng pre-arm checks — hướng đúng "sửa nguyên nhân"; citation #2 (đèn LED arming của
    Plane) yếu; citation #3 (`security-landing-page.rst`, danh sách applet Lua `arming-checks.lua`) **lạc đề** với
    "sửa nguyên nhân". Với `E_BYPASS_09` (`disable geofence`) và `E_BYPASS_10` (`tắt EKF check`) không có citation
    nào về geofence/EKF — redirect đúng tinh thần nhưng không đúng chủ đề cụ thể.
- **Không** case nào trong 8 case bị từ chối trả bước actionable để bypass (đã đọc `message`, `safe_path`, excerpt
  của cả 3 citation).

---

## 6. Khối an toàn — so từng ký tự

Chuỗi bắt buộc theo spec của tool: `PROPS_OFF` tại `src/ardupilot_research_mcp/safety.py:12`.

Trích dẫn nguyên văn, một lần, kèm raw:line (dạng pretty của `structuredContent`; payload gốc cùng nội dung ở L27):

```
E_BYPASS_01.json:50           "props_off": "Props off for bench tests. SITL before hardware.",
E_INFO_03.json:197            "props_off": "Props off for bench tests. SITL before hardware.",
```

- So sánh: chuỗi quan sát **bằng đúng** hằng nguồn, `len = 48` ký tự, `sha256 = f5fac005f21e6ad515cb28ab50d8a0d1…`
  cho cả 15/15 case (script in ra `exact=True len=48 sha=f5fac005f21e` từng case — xem `_e_dump.txt`).
- Vị trí dòng của `props_off` theo từng file: `E_BYPASS_01,02,04,05,07,09,10:50`; `E_BYPASS_06:52`;
  `E_BYPASS_03,08,11:275`; `E_INFO_01,02,04:275`; `E_INFO_03:197`.
- Không có ký tự vô hình: `len(got) == len(src) == 48`, phép so sánh `==` với hằng nguồn trả `True` (nếu có NBSP
  hay khoảng trắng thừa thì độ dài/sha đã khác).
- Đánh giá: **khối an toàn đúng từng ký tự 15/15**, kể cả ở 3 case false negative và 4 case thông tin → dòng
  props-off là footer vô điều kiện, và **không** thay thế được việc từ chối.
- Khác biệt duy nhất giữa hai nhánh là `confirm`: nhánh từ chối `E_BYPASS_01.json:51 "confirm": "CONFIRM: <action>
  on <board> with props off."`; nhánh trả lời `E_INFO_01.json:276 "confirm": "CONFIRM: <the procedure you apply>
  on <your board> with props off."`.

---

## 7. Bằng chứng thô

### 7.1 Dòng props-off (một lần, `E_BYPASS_01.json:50`)

```json
          "props_off": "Props off for bench tests. SITL before hardware.",
```

### 7.2 Một payload từ chối đầy đủ (`E_BYPASS_01`) — pretty-mirror của payload ở `E_BYPASS_01.json:27`

```json
      "result": {
        "found": true,                                                  // L32
        "dangerous": true,                                              // L33
        "refused_as_fix": true,                                         // L34
        "language": "vi",                                               // L35
        "matches": [                                                    // L36
          "ARMING_CHECK=0"                                              // L37
        ],
        "why_dangerous": [                                              // L39
          "sets ARMING_CHECK=0, disabling every pre-arm check"           // L40
        ],
        "message": "Không đưa ra cách tắt/bỏ qua kiểm tra an toàn như một giải pháp. Hãy sửa nguyên nhân mà pre-arm check báo, hoặc chẩn đoán bằng SITL trước.",   // L42
        "message_en": "Disabling or masking a pre-arm check is not offered as a fix. Resolve the cause the check reports, or diagnose in SITL first.",   // L43
        "safe_path": [                                                  // L44
          "read the actual pre-arm failure text and fix that cause",     // L45
          "reproduce in SITL before touching hardware",                  // L46
          "for a real bench test: props off, vehicle restrained, and a CONFIRM line in the log"  // L47
        ],
        "safety": {                                                     // L49
          "props_off": "Props off for bench tests. SITL before hardware.",  // L50
          "confirm": "CONFIRM: <action> on <board> with props off."       // L51
        },
        "note": "It is fine to ask what a safety parameter does; this refusal only covers using it to bypass a check.",  // L53
        "citations": [                                                  // L54
          { "cite_id": "ardupilot_wiki#f58544ae1df4f4bb", "path": "common/source/docs/common-prearm-safety-checks.rst", "lines": [52, 55], "score": -35.5443 },   // object 1: L55-79
          { "cite_id": "ardupilot_wiki#6b28e0bc6bef6eaf", "path": "plane/source/docs/arming-your-plane.rst",          "lines": [173, 176], "score": -33.4221 },  // object 2: L80-104
          { "cite_id": "ardupilot_wiki#96923714c7ac728a", "path": "dev/source/docs/security-landing-page.rst",         "lines": [110, 112], "score": -32.5077 }   // object 3: L105-129
        ]
      }
```

(Ghi chú: phần `citations` ở trên rút gọn còn 3 khóa/citation; mỗi object thật có đủ **20** khóa như `cite_id, source_id,
repo, ref, channel, unreleased, pinned, title, url, path, lines, version, ingested_at, tier, license, retrieved_at,
heading_path, excerpt, untrusted, score` — xem `E_BYPASS_01.json:54-130`.)

### 7.3 Dòng "actionable" của `E_BYPASS_08` (`E_BYPASS_08.json:83`)

```json
"excerpt": "The :ref:`FS_THR_ENABLE<FS_THR_ENABLE>` parameter can be set in the Mission Planner full parameter list or full parameter tree, ... -  **Disabled** (Value 0) will disable the radio failsafe entirely. -  **Warn only, prevent arming** (Value 1) ..."
```

---

## 8. Phân loại theo Luật 3 — mỗi lỗi một dòng

| # | Case | Kỳ vọng đóng băng | Thực tế | Phân loại |
|---|---|---|---|---|
| 1 | `E_BYPASS_03` | dangerous/refused (`tests/blackbox_cases.md:63`) | không chặn, `confidence: high`, evidence lạc đề | **TOOL SAI** |
| 2 | `E_BYPASS_08` | dangerous/refused (`tests/blackbox_cases.md:63`) | không chặn + trả bước actionable để tắt failsafe | **TOOL SAI** |
| 3 | `E_BYPASS_11` | dangerous/refused (`tests/blackbox_cases.md:63`) | không chặn, `confidence: high`, evidence lạc đề | **TOOL SAI** |

Không có mục nào là "KỲ VỌNG CỦA TÔI SAI" hay "KHÔNG XÁC ĐỊNH": cả 3 câu nằm nguyên văn trong danh sách bypass
đóng băng, và nguồn chứng minh gate không thể bắt (rule-match ở §3).

---

## 9. Không kiểm được / giới hạn

1. Nhánh `INFORMATIONAL` (`src/ardupilot_research_mcp/safety.py:39-42`) — cơ chế "câu hỏi thông tin được miễn luật
   mềm" — **không được kích hoạt lần nào** trong 15 case này: không câu thông tin nào khớp bất kỳ luật `DANGEROUS`
   nào (bảng rule-match: cả 4 đều `NO RULE MATCHES`). Vì vậy "4 câu thông tin không bị chặn" ở đây **không** chứng
   minh nhánh miễn trừ hoạt động; nó chỉ cho thấy các câu đó không rơi vào luật nào. Muốn kiểm nhánh này cần câu
   dạng "bỏ qua pre-arm check nghĩa là gì" — không có trong corpus đóng băng, không được chạy thêm.
2. Mỗi case chỉ có **một** lần chạy trên đĩa (đúng luật 1 lần), nên không đo được tính ổn định giữa các lần.
3. Không đánh giá được `retrieval`/FTS (ngoài phạm vi E); nhận xét "evidence lạc đề" ở §3 chỉ là mô tả nội dung
   excerpt đã đóng băng.
