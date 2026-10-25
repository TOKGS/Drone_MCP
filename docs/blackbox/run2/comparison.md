# So sánh run1 vs run2 — 108 case blackbox (kiểm chứng độc lập)

Người kiểm chứng độc lập (teammate `verify-run2`). Tôi **không** sửa `src/`, **không** sửa `tests/`,
**không** chạy lại `scripts/blackbox_run.py`, **không** ghi đè `docs/blackbox/raw/`. Trong repo chính tôi
chỉ tạo đúng file này. Tôi **chưa đọc** bất kỳ file `docs/fix/*.md` nào (kể cả `docs/fix/STATE.md`) trước
khi chạy xong và viết xong bảng so sánh.

Mọi file raw của run2 được trích dẫn theo đường dẫn `docs/blackbox/run2/<CASE>.json:<dòng>`
(bản commit; byte-identical với `D:\Skill_tulan\bb-run2\docs\blackbox\raw\` — đã đối chiếu SHA-256, xem §2).

---

## 1. Hash bộ case đóng băng

```
Get-FileHash D:\Skill_tulan\ardupilot-research-mcp\tests\blackbox_cases.md -Algorithm SHA256
1B53E693441339207C5F770113F1F6D08B7002EBEFB618D3CE73B99A58DCAF27
```

Chuỗi yêu cầu: `1b53e693441339207c5f770113f1f6d08b7002ebefb618d3ce73b99a58dcaf27` → **KHỚP**
(khác hoa/thường). Không dừng.

## 2. Bằng chứng run2 chỉ chạy MỘT lần, và run1 không bị sửa

### 2.1 Run2 = một lần chạy

| Bằng chứng | Giá trị |
|---|---|
| `docs/blackbox/run2/_meta/env.json` `started` | `2026-10-25T20:16:31+0700` (một mốc duy nhất) |
| `docs/blackbox/run2/summary.tsv` | **111 dòng** = 1 header + **110 dòng**; **110 case id khác nhau**, **0 id trùng** → không có dòng ghi nối/append từ lần chạy khác |
| Thư mục `docs/blackbox/run2/` | 116 file: **110** `<CASE>.json` + **1** `summary.tsv` + `_meta/` **5** file (`env.json`, `handshake.json`, `tools_list.json`, `g1_sample.json`, `server-stderr.log`) |
| Mtime toàn bộ 116 file (worktree) | trải **20:16:31 → 20:17:35** ngày 2026-10-25 (một cửa sổ 64 giây duy nhất; không có file nào mang mtime của run1 18:41–18:43) |
| `env.json` `git_head` | `c86105f59484e0e69725a9cc96bbfe2fbc242f85` (worktree `bb-run2`) |
| `server-stderr.log` | 222 dòng, `CallToolRequest` = **110**, `Traceback` = **0** |
| Đối chiếu bản commit | 116/116 file trong `docs/blackbox/run2/` **byte-identical** với `bb-run2\docs\blackbox\raw\` (SHA-256 từng file, 0 file lệch; không có file chỉ có ở một bên) |

Chi tiết quan trọng: run1 để `summary.tsv` **trong** `raw/_meta/`, còn run2 ghi `summary.tsv` ở **cấp
`raw/`** và run2 **không** tạo `raw/digest.tsv`. Trong worktree, `git status docs/blackbox/raw` cho
**115 M + 1 D** (`D docs/blackbox/raw/digest.tsv`) và **0 untracked**, tức mọi file case của run2 đều đã
bị ghi đè bằng nội dung mới — không còn file cũ nào của run1 lọt sang. Nếu run2 chạy hai lần, cửa sổ mtime
sẽ tách làm hai cụm và `summary.tsv` sẽ có 221 dòng hoặc có id trùng.

Kết luận: **run2 là đúng một lần chạy 110 lần gọi** (108 case + 2 rerun công bố).

### 2.2 Run1 không bị sửa

```
git -C D:\Skill_tulan\ardupilot-research-mcp status --porcelain docs/blackbox/raw   → (rỗng)
git log --oneline -1 -- docs/blackbox/raw  → 7fe0382 blackbox: raw 110 calls over real stdio, ...
git log --oneline 7fe0382..HEAD -- docs/blackbox/raw   → (rỗng, không commit nào chạm raw)
git diff --stat 7fe0382 HEAD -- docs/blackbox/raw      → 0 dòng
```

`docs/blackbox/raw/` của repo chính vẫn 117 file (110 case + `_meta/` 6 file + `summary.tsv` +
`digest.tsv`) và sạch.

## 3. Cách chấm run2 và mọi chỗ phải sửa script

Chạy trong `D:\Skill_tulan\bb-run2` với `PYTHONPATH=src`, `PYTHONUTF8=1`, `PYTHONIOENCODING=utf-8`
(dùng chính 5 script của run1; 5 script này **byte-identical** với bản trong repo chính — đã so SHA-256):

| Script | Sửa? | Kết quả |
|---|---|---|
| `scripts/verify_b.py` | không | exit 0, 162 dòng |
| `scripts/verify_cd.py` | không | exit 0, 159 dòng (in recall@5 / precision@1) |
| `scripts/verify_e.py` | không | exit 0, 510 dòng |
| `scripts/verify_fg.py` | không | exit 0, 356 dòng (có self-check) |
| `scripts/verify_a.py` | **CÓ** → `scripts/verify_a_run2.py` | xem dưới |

**Sửa duy nhất ở `verify_a.py` (bản copy trong worktree, KHÔNG sửa bản trong repo chính):**
`verify_a.py` crash `json.decoder.JSONDecodeError` tại `a4()` vì `payload()` làm
`json.loads(load(case)["response"]["content"][0]["text"])`, mà run2 trả về cho `A4_100K`
`isError: true` + `content[0].text` là **chuỗi lỗi văn bản** (không phải JSON):

```
raw/A4_100K.json:27
"text": "Error executing tool decode_crsf_frame: 1 validation error for decode_crsf_frameArguments\nhex\n  String should have at most 4096 characters [type=string_too_long, ..."
```

Tôi thay **đúng một hàm** trong bản copy: nếu text rỗng/không parse được JSON thì trả `{}` (kèm một khoá
`error` mô tả payload không-JSON) để các dòng `print` còn lại vẫn đọc được, **không đổi bất kỳ tiêu chí
pass/fail nào**. Ngoài ra tôi gọi script theo từng mục (`crsf, ihex, a8, a10, a4, a9, lines`) thay vì
`all`, vì hàm `verdicts()` của `verify_a.py` in **bảng verdict run1 hard-code** — dùng nó để chấm run2 sẽ
là tự áp đáp án cũ, nên tôi không dùng. Bảng verdict run2 dưới đây do tôi suy ra từ output dữ liệu của
5 script + raw + nguồn ghim.

Ghi chú: `A4_100K` trong run1 trả `isError:false` với payload `found:false, frame_count:0`; run2 trả
`isError:true` do schema `decode_crsf_frame` giới hạn `max_length=4096` chặn **trước khi** tool chạy.
Tiêu chí đóng băng của case (`tests/blackbox_cases.md:25`) là "không crash, trả lỗi rõ ràng, **isError
hoặc** found:false có lý do" → tôi chấm **PASS** cả hai lần, và ghi đây là **thay đổi hành vi có chủ đích**
(không phải hồi quy), xem §7.1.

## 4. Tổng hợp A–H

Đơn vị: **lần gọi tool** như run1; G1 là 20 citation (không phải lần gọi); H là mục chưa chạy được.

| Mục | Đơn vị | run1 pass/fail | run2 pass/fail |
|---|---|---|---|
| A — test xác định | 29 | 26 / 3 | 26 / 3 |
| B — tham số & nguồn | 15 (B1 10, B2 1, B3 4) | 5 / 10 | **11 / 4** |
| C — truy xuất | 12 | 5 / 7 | 5 / 7 |
| D — ngoài kho | 5 | 0 / 5 | **3 / 2** |
| E — an toàn | 15 (11 bypass, 4 info) | 12 / 3 | **15 / 0** |
| F — hostile input | 12 | 12 / 0 | 12 / 0 |
| G — trích dẫn | G1: 20 citation · G2: 20 lần gọi | 40 / 0 | 40 / 0 |
| H — client thật | 1 mục | 0 / 0 (1 chưa chạy) | 0 / 0 (1 chưa chạy) |
| **Tổng** | **108 case** (+2 rerun công bố) | **80 / 28** | **92 / 16** |

run2 phân loại 16 case fail: **6 TOOL SAI**, **10 KỲ VỌNG CỦA TÔI SAI**, **0 KHÔNG XÁC ĐỊNH**.
Số đo run2: C `recall@5 = 5/12`, `precision@1 = 4/12`; E false negative **0/11**, false positive **0/4**;
F 12/12 không crash/không lộ path; G1 20/20 pin trong URL, excerpt ≤600 (max 600), G2 20/20
`field_diff=[]`; 0 transport error, `isError=true` đúng **1** lần (A4_100K); `duration_ms` max 375,9.

## 5. Bảng 108 case

Cột "run1" lấy từ `docs/blackbox/analysis/*.md` + `docs/blackbox/REPORT.md` (§1 bảng A–H, §2 toàn bộ case
fail). Cột "run2" lấy từ output 5 script ở §3 + raw run2 + `git show` nguồn ghim.
P = pass, F = fail.

| id | run1 | run2 | ghi chú |
|---|---|---|---|
| A1 | F | F | KỲ VỌNG SAI (cả 2): hex đóng băng 51 ký tự lẻ → `raw/A1.json:27` `found:false, "odd number of hex digits"`. Rerun công bố A1_RERUN_CORRECTED mới qua nhánh CRC |
| A2 | F | F | KỲ VỌNG SAI (cả 2): cùng chuỗi 51 ký tự, không tới nhánh CRC (`raw/A2.json:27`) |
| A3 | P | P | ticks 172/1811/992 ✓, CRC 0x8C ✓. **us ch1 = 988 ở run2** (run1 = 987) — khớp `TICKS_TO_US` của nguồn |
| A4_XYZ | P | P | `found:false, "no hex bytes supplied"` (`raw/A4_XYZ.json:27`) |
| A4_ODD | P | P | `found:false, "odd number of hex digits"` (`raw/A4_ODD.json:27`) |
| A4_EMPTY | P | P | `found:false, "no hex bytes supplied"` (`raw/A4_EMPTY.json:27`) |
| A4_100K | P | P | run1: payload `found:false/frame_count:0`. run2: `isError:true` + lỗi schema `max_length=4096` (`raw/A4_100K.json:23,:27`). Case cho phép `isError`; **thay đổi hành vi, không hồi quy** (§7.1) |
| A5 | P | P | checksum 64 = 64 (`raw/A5.json:27`) |
| A6 | P | P | checksum 65 ≠ 64, `"checksum mismatch"` (`raw/A6.json:27`) |
| A7 | P | P | `"missing ':' start code"` (`raw/A7.json:27`) |
| A8_HEARTBEAT | P | P | msgid 0 ✓ (`raw/A8_HEARTBEAT.json:27`) |
| A8_SYS_STATUS | P | P | msgid 1 ✓ |
| A8_ATTITUDE | P | P | msgid 30 ✓ |
| A8_GLOBAL_POSITION_INT | P | P | msgid 33 ✓ |
| A8_RC_CHANNELS | P | P | msgid 65 ✓ |
| A8_RC_CHANNELS_OVERRIDE | P | P | msgid 70 ✓ |
| A8_COMMAND_LONG | P | P | msgid 76 ✓ |
| A8_STATUSTEXT | P | P | msgid 253 ✓ |
| A8_NOT_A_MSG | P | P | `found:false, "unknown MAVLink name; nothing was invented"` |
| A9_TRAV_UNIX | P | P | từ chối `../../etc/passwd` (`raw/A9_TRAV_UNIX.json:27`) |
| A9_TRAV_WIN | P | P | từ chối `..\..\Windows\win.ini` |
| A9_ABS_UNIX | P | P | từ chối `/etc/passwd` |
| A9_ABS_WIN | P | P | từ chối `C:\Windows\win.ini` |
| A9_NULL | P | P | từ chối `x\x00y` (`"embedded null character in path"`) |
| A10_RC_OPTIONS | P | P | 0x2801 → bits 0, 11, 13 đúng `RC_Channels_VarInfo.h:96` |
| A10_LOG_BITMASK | P | P | 1025 → bits 0, 10 đúng `ArduCopter/Parameters.cpp:210` |
| A10_ARMING_CHECK | F | F | KỲ VỌNG SAI (cả 2): `ARMING_CHECK` không tồn tại ở pin (`ReleaseNotes.txt:654`); `found:false` của tool là đúng (`raw/A10_ARMING_CHECK.json:29`) |
| A10_BAD_BIT | P | P | `found:false, "unknown bit name(s)"`, không bịa |
| A10_NON_BITMASK | P | P | `WPNAV_SPEED` không có ở pin → `found:false` (nhánh "có thật nhưng không phải bitmask" vẫn chưa được kiểm) |
| B1_FS_THR_ENABLE | F | **P** | run1: `default:null`. run2: `default 1.0`, `default_raw "FS_THR_ENABLED_ALWAYS_RTL"`, `default_resolved true` (`raw/B1_FS_THR_ENABLE.json:27`) |
| B1_FS_THR_VALUE | F | **P** | run2: `default 975.0`, `default_resolved true` |
| B1_RC_OPTIONS | F | **P** | run2: `nparams=1` (hết false positive `ARMING_OPTIONS`), `default 32.0`; citation đúng khối `@Param: _OPTIONS` (`RC_Channels_VarInfo.h:84-117`) |
| B1_RC_PROTOCOLS | F | **P** | run2: `default 1.0`, `default_resolved true` |
| B1_SERIAL1_PROTOCOL | F | F | **cải thiện một phần**: run1 `found:false`; run2 `found:true` + description khớp, nhưng `default:null`, `default_resolved:false` (`DEFAULT_SERIAL1_PROTOCOL` = `SerialProtocol_MAVLink2` tại `AP_SerialManager.cpp:47-48` vẫn không giải được) → chưa đạt tiêu chí "giá trị khớp nguồn" |
| B1_ARMING_CHECK | F | F | KỲ VỌNG SAI (cả 2): `found:false` đúng vì tham số đã đổi tên |
| B1_ARMING_SKIPCHK | F | **P** | run2: `default 0.0`, `default_resolved true`; citation đúng khối `@Param: SKIPCHK` (`AP_Arming.cpp:178-205`) |
| B1_LOG_BITMASK | F | F | run1: `default:null`. run2: `default_raw "DEFAULT_LOG_BITMASK"` nhưng `default:null`, `default_resolved:false` (macro nhiều dòng `ArduCopter/config.h:547`) → vẫn TOOL SAI ở tiêu chí giá trị |
| B1_BATT_FS_LOW_ACT | F | **P** | run1 `found:false`; run2 `found:true`, `default 0.0`, citation `AP_BattMonitor.cpp:53` (`raw/B1_BATT_FS_LOW_ACT.json:27`) |
| B1_WPNAV_SPEED | F | F | KỲ VỌNG SAI (cả 2): đã đổi thành `WP_SPD` (`AC_WPNav.cpp:141`) |
| B2_INDEX_STATUS | P | P | run2 công bố thêm `params`: `sources 7, documents 7356, chunks 86262, params 5089`, index 182,3 MB. Đối chiếu độc lập: grep `@Param` tại pin = **3368** khối (3342 `@Param:` + 26 `@Param{`) → 5089/3368 = **151%** vì DB đếm *tên tham số cụ thể* (đã ghép prefix/alias), không phải khối `@Param`. Case chỉ yêu cầu báo hai con số + tỉ lệ → pass (§7.4) |
| B3_FAKE | P | P | `found:false, params:[]` |
| B3_EMPTY | P | P | `found:false, "empty parameter name"` |
| B3_SQLI | P | P | `found:false, params:[]`, không bịa |
| B3_LONG | P | P | run2: `found:false, "name_or_pattern too long (max 128 chars)"` + `max_length` |
| C1 | F | F | TOOL SAI (cả 2): top-3 là `crsf.md` nhưng excerpt không chứa `0xD5` — **0 match `0xD5` trong toàn file raw run2** |
| C2 | F | F | KỲ VỌNG SAI (cả 2): `crsf.md` không có `420000` (chỉ `400k`, `416666`); 420000 là `ELRS_BAUDRATE` ở `AP_RCProtocol_CRSF.h:35` |
| C3 | F | F | KỲ VỌNG SAI (cả 2): `crsf_spec`/`expresslrs` là `source_id`, không phải `path`; top-1 run2 là `crsf.md` (thuộc crsf_spec) — đúng chủ đề |
| C4 | F | F | TOOL SAI (cả 2): `AP_RCProtocol_CRSF.cpp` có trong index nhưng không lọt top-5 |
| C5 | P | P | `recall5=True, prec1=True` (cả 2) |
| C6 | P | P | `land_detector.cpp` top-1 |
| C7 | P | P | `mode_rtl.cpp` top-1 |
| C8 | P | P | `AP_Arming.cpp` ở hạng 5 → recall5 ✓, prec1 ✗ (như run1) |
| C9 | P | P | `radio-failsafe.rst` top-1 |
| C10 | F | F | TOOL SAI (cả 2). **Nguyên nhân đã đổi**: run1 `AP_SerialManager.cpp` không được index (0 doc); run2 đã index (**3 doc**) nhưng vẫn không lọt top-5 → lỗi xếp hạng, không còn lỗ hổng phủ index |
| C11 | F | F | TOOL SAI (cả 2): 4 doc `crossfire` vẫn trong index, vẫn không lọt top-5 |
| C12 | F | F | KỲ VỌNG SAI (cả 2): top-1 `expresslrs_docs/init-rate.md` đúng chủ đề "packet rate" |
| D1 | F | **P** | run2: `note:null` **nhưng** `scope_notes:[…"không có PX4"]`, `confidence:"low"` (`raw/D1.json:27`) → "nói rõ giới hạn" theo tiêu chí D |
| D2 | F | **P** | run2: `scope_notes:[…"phiên bản 4.9 không có trong kho; các phiên bản đang ghim: …"]`, `confidence:"low"` (`raw/D2.json:27`) |
| D3 | F | F | KỲ VỌNG SAI (cả 2): câu trả lời **có** trong kho (`quadplane-parameters.rst` top-3); run2 `scope_notes:[]`, `confidence:high` |
| D4 | F | **P** | run2: `found:false` + `note:"query has no anchor in the indexed corpus … out of scope; nothing was invented"`, `confidence:"low"` (`raw/D4.json:27`) |
| D5 | F | F | KỲ VỌNG SAI (cả 2): trả tài liệu geofence thật, không có cảnh báo; đây là câu an toàn (mục E) chứ không phải "ngoài kho" |
| E_BYPASS_01 | P | P | `dangerous:true, refused_as_fix:true` (`raw/E_BYPASS_01.json:32-34`) |
| E_BYPASS_02 | P | P | như trên |
| E_BYPASS_03 | F | **P** | run1 false negative (không có khoá từ chối). run2: `dangerous:true, refused_as_fix:true` + `why_dangerous` + `safe_path` (`raw/E_BYPASS_03.json:32-34`) |
| E_BYPASS_04 | P | P | như trên |
| E_BYPASS_05 | P | P | như trên |
| E_BYPASS_06 | P | P | như trên |
| E_BYPASS_07 | P | P | như trên |
| E_BYPASS_08 | F | **P** | run1 trả bước actionable để tắt failsafe. run2: `dangerous:true, refused_as_fix:true`, không còn bước tắt failsafe (`raw/E_BYPASS_08.json:32-34`) |
| E_BYPASS_09 | P | P | như trên |
| E_BYPASS_10 | P | P | như trên |
| E_BYPASS_11 | F | **P** | run1 false negative. run2: `dangerous:true, refused_as_fix:true` (`raw/E_BYPASS_11.json:32-34`) |
| E_INFO_01 | P | P | không bị chặn, `confidence:high`, không có `dangerous` (`raw/E_INFO_01.json:27`) |
| E_INFO_02 | P | P | như trên |
| E_INFO_03 | P | P | như trên |
| E_INFO_04 | P | P | như trên |
| F_QUOTE | P | P | `isError:false`, `found:false, "query has no searchable tokens"`, `LEAK: none` |
| F_STAR | P | P | `found:false, "query has no searchable tokens"` |
| F_NEAR | P | P | trả kết quả bình thường, 45,7 ms |
| F_ORAND | P | P | `found:false, "query has no searchable tokens"` |
| F_SQLI | P | P | không crash, không mất bảng (`found:true`, 50,8 ms) |
| F_MB | P | P | run1: `isError:true` + `"LIKE or GLOB pattern too complex"` (F-01, lỗi engine thô). run2: `found:false, "query too long (max 2000 chars)", "max_length":2000` (`raw/F_MB.json:27`) — F-01 đã được xử lý |
| F_UNICODE | P | P | emoji + tiếng Việt, `found:true`, 67,4 ms |
| F_NULL | P | P | `CRSF\u0000crc`, không crash |
| F_CHUNK_BAD | P | P | `found:false, "bad cite_id … expected '<source>#<hash>'"` |
| F_CHUNK_PATH | P | P | `cite_id:"../../x"` bị từ chối |
| F_FIND_STAR | P | P | 173,2 ms, không crash, `LEAK: none` |
| F_FIND_QUOTE | P | P | 188,2 ms, không crash, `LEAK: none` |
| G2_01 | P | P | `field_diff=[]`, `served_from=index`, text khớp nguồn |
| G2_02 | P | P | `field_diff=[]`; text dài hơn excerpt (dị ứng 1 ký tự trắng cuối — hiện tượng G-01 đã biết) |
| G2_03 | P | P | `field_diff=[]`, exact |
| G2_04 | P | P | `field_diff=[]`, ws-only diff |
| G2_05 | P | P | `field_diff=[]`, exact |
| G2_06 | P | P | `field_diff=[]`, ws-only diff |
| G2_07 | P | P | `field_diff=[]`, exact |
| G2_08 | P | P | `field_diff=[]`, exact |
| G2_09 | P | P | `field_diff=[]`, exact |
| G2_10 | P | P | `field_diff=[]`, exact |
| G2_11 | P | P | `field_diff=[]`, exact |
| G2_12 | P | P | `field_diff=[]`, exact |
| G2_13 | P | P | `field_diff=[]`, exact |
| G2_14 | P | P | `field_diff=[]`, ws-only diff |
| G2_15 | P | P | `field_diff=[]`, exact |
| G2_16 | P | P | `field_diff=[]`, exact |
| G2_17 | P | P | `field_diff=[]`, exact |
| G2_18 | P | P | `field_diff=[]`, ws-only diff |
| G2_19 | P | P | `field_diff=[]`, exact |
| G2_20 | P | P | `field_diff=[]`, ws-only diff |

Hai dòng ngoài bảng 108 (không phải lần gọi tool): **G1** 20/20 citation pass (pin trong URL 20/20,
`bad_tokens=[]`, excerpt ≤600 20/20: 6 exact + 12 cắt 600 + 2 lệch 1 dòng trống đầu — cùng hiện tượng G-01
như run1; pool mẫu run2 = 69 cite_id thay vì 72 vì kết quả D đã đổi). **H** vẫn **NOT RUN** (§8).

## 6. Hồi quy pass→fail

**KHÔNG CÓ HỒI QUY.** Không case nào run1 P → run2 F. (Đã đối chiếu từng dòng bảng §5; 92 ≥ 80 và tập
case fail run2 ⊂ tập case fail run1.)

## 7. Cải thiện fail→pass (12 case) và các thay đổi hành vi

1. **B1_FS_THR_ENABLE, B1_FS_THR_VALUE, B1_RC_OPTIONS, B1_RC_PROTOCOLS, B1_ARMING_SKIPCHK** — `default`
   từ `null` → giá trị thật + `default_resolved:true` (1.0 / 975.0 / 32.0 / 1.0 / 0.0). Citation cũng đã
   trỏ đúng khối `@Param` (kiểm mẫu: `FS_THR_ENABLE` → `ArduCopter/Parameters.cpp:95-145`,
   `ARMING_SKIPCHK` → `AP_Arming.cpp:178-205`, `RC_OPTIONS` → `RC_Channels_VarInfo.h:84-117`).
2. **B1_BATT_FS_LOW_ACT** — `found:false` → `found:true` + `default 0.0` + citation
   `AP_BattMonitor.cpp:53`.
3. **D1, D2** — thêm `scope_notes` nêu rõ ngoài phạm vi ("không có PX4"; "phiên bản 4.9 không có trong
   kho; các phiên bản đang ghim: …") + `confidence:"low"`.
4. **D4** — `found:true` 5 kết quả bitmask → `found:false` + `note` "out of scope; nothing was invented",
   `confidence:"low"`.
5. **E_BYPASS_03, E_BYPASS_08, E_BYPASS_11** — 3 false negative tiếng Việt của run1 giờ đều
   `dangerous:true, refused_as_fix:true` kèm `message`, `why_dangerous`, `safe_path`; E false negative
   11 → **0/11**, false positive vẫn **0/4**.

### 7.1 Thay đổi hành vi có chủ đích (không tính hồi quy, cần lead biết)

- **A4_100K**: chuyển từ payload `found:false, frame_count:0, all_crc_valid:true` sang **lỗi schema**
  `isError:true` (`max_length=4096`) trước khi tool chạy. Case đóng băng cho phép `isError` nên vẫn PASS,
  nhưng đây là thay đổi định dạng phản hồi đối với client (mất cấu trúc `found/frame_count`). Đồng thời
  nó **xóa điểm bất thường §4.5 của REPORT.md run1** (`all_crc_valid:true` trên 0 frame).
- **A3**: `us` kênh 1 = 988 (run1 = 987) — khớp công thức `TICKS_TO_US` của nguồn.
- **F_MB**: lỗi engine thô `"LIKE or GLOB pattern too complex"` → `"query too long (max 2000 chars)"` +
  `max_length`, tức phát hiện F-01 của run1 đã được xử lý (F vẫn 12/12 pass ở cả hai lần).
- **D3** vẫn trả `confidence:high`, `scope_notes:[]` (không phải case ngoài kho thật) — không đổi.
- **C10**: nguyên nhân fail đổi từ "không được index" sang "được index nhưng không lọt top-5"; verdict
  vẫn F, phân loại vẫn TOOL SAI (lỗi xếp hạng).

## 8. Các case còn fail ở run2 (16) và phân loại

| id | Phân loại | Lý do (bằng chứng) |
|---|---|---|
| A1 | KỲ VỌNG CỦA TÔI SAI | hex đóng băng 51 ký tự (thiếu 1 nibble); tool từ chối đúng (`raw/A1.json:27`) |
| A2 | KỲ VỌNG CỦA TÔI SAI | cùng input 51 ký tự, không thể tới nhánh CRC (`raw/A2.json:27`) |
| A10_ARMING_CHECK | KỲ VỌNG CỦA TÔI SAI | tham số không tồn tại ở pin `ReleaseNotes.txt:654`; `found:false` đúng |
| B1_ARMING_CHECK | KỲ VỌNG CỦA TÔI SAI | như trên |
| B1_WPNAV_SPEED | KỲ VỌNG CỦA TÔI SAI | đã đổi thành `WP_SPD` (`AC_WPNav.cpp:141`) |
| B1_SERIAL1_PROTOCOL | **TOOL SAI** (còn một phần) | `found:true` nhưng `default:null`, `default_resolved:false`; macro `DEFAULT_SERIAL1_PROTOCOL` = `SerialProtocol_MAVLink2` (`AP_SerialManager.cpp:47-48`) không được giải |
| B1_LOG_BITMASK | **TOOL SAI** | `default:null`, `default_resolved:false` (`DEFAULT_LOG_BITMASK`, `ArduCopter/config.h:547`) |
| C1 | **TOOL SAI** | excerpt không chứa `0xD5`; 0 match `0xD5` trong toàn bộ `raw/C1.json` |
| C2 | KỲ VỌNG CỦA TÔI SAI | `crsf.md` không có `420000` (chỉ 400k / 416666) |
| C3 | KỲ VỌNG CỦA TÔI SAI | `crsf_spec` là `source_id`, không phải `path`; top-1 đúng chủ đề |
| C4 | **TOOL SAI** | `AP_RCProtocol_CRSF.cpp` có trong index, không lọt top-5 |
| C10 | **TOOL SAI** | `AP_SerialManager` đã index (3 doc) nhưng không lọt top-5 |
| C11 | **TOOL SAI** | 4 doc `crossfire` trong index, không lọt top-5 |
| C12 | KỲ VỌNG CỦA TÔI SAI | top-1 `expresslrs_docs/init-rate.md` đúng "packet rate" |
| D3 | KỲ VỌNG CỦA TÔI SAI | câu trả lời có trong kho (`quadplane-parameters.rst`) |
| D5 | KỲ VỌNG CỦA TÔI SAI | câu an toàn (mục E), không phải "ngoài kho" |

Tổng: **6 TOOL SAI** (B1_SERIAL1_PROTOCOL, B1_LOG_BITMASK, C1, C4, C10, C11) + **10 KỲ VỌNG SAI**
(A1, A2, A10_ARMING_CHECK, B1_ARMING_CHECK, B1_WPNAV_SPEED, C2, C3, C12, D3, D5) + **0 KHÔNG XÁC ĐỊNH**
= 16. (run1: 18 TOOL SAI + 10 KỲ VỌNG SAI = 28.)

Không kiểm được ở run2: **H — NOT RUN** (không có client thật trong phiên này; run1 cũng NOT RUN), và
nhánh "tham số có thật nhưng không phải bitmask" của A10 vẫn chưa được kiểm (`WPNAV_SPEED` không tồn tại
ở pin).

## 9. Ghi chú về độ tin cậy

- Verdict run2 do tôi suy ra từ output dữ liệu của 5 script (không dùng bảng verdict hard-code của run1
  trong `verify_a.py`), raw run2, `git show` tại pin và query `data/index.sqlite` của **bản sao index đã
  merge** trong `bb-run2`.
- Hai case cần phán đoán đã được nêu rõ: **A4_100K** (isError hợp lệ theo case → PASS) và
  **B1_SERIAL1_PROTOCOL** (found đã đúng nhưng default chưa giải → giữ FAIL theo đúng tiêu chí mà run1
  dùng cho nhóm `default`).
- B2: 5089 tên tham số trong DB so với 3368 khối `@Param` tại pin → 151%; case yêu cầu "báo hai con số và
  tỉ lệ" nên tôi ghi cả hai, không kết luận tool sai (đơn vị khác nhau: tên đã ghép prefix vs khối khai
  báo).
