# Nhật ký nhánh fix/A — lỗi 3 → 1 → 2

Worktree `D:\Skill_tulan\wt-A`, nhánh `fix/A`, base `7fe0382`. Mọi lệnh chạy từ gốc worktree với
`$env:PYTHONPATH='src'`, `$env:ARM_REPO_ROOT='D:\Skill_tulan\wt-A'`, `GOVERNOR_HOME=D:\Skill_tulan\wt-A\research`.
Pin của clone: `fb773567896014da007bca58358704d4a0d8516f` (`git -C research/cache/git/ardupilot rev-parse HEAD`).

## A-0. Đo mốc (trước khi sửa bất cứ gì)

```
PS> python -c "import sys; sys.path.insert(0,'src'); from ardupilot_research_mcp import db; import json; print(json.dumps(db.counts(db.connect())))"
{"sources": 7, "documents": 4908, "chunks": 65509, "params": 230, "mavlink_msgs": 397, "mavlink_enums": 2367}

PS> (Get-Item data\index.sqlite).Length/1MB
123.125
```

Khớp kỳ vọng: `params=230`, index ~123 MB.

### Lệnh lỗi gặp phải (nguyên văn, C2)

Brief dặn dựng lại index theo mục "How to reproduce" của `FINAL_REPORT.md`. File này **không tồn
tại** trong worktree (`FINAL_REPORT.md` nằm ở `.gitignore`), lỗi nguyên văn:

```
Select-String : Cannot find path 'D:\Skill_tulan\wt-A\FINAL_REPORT.md' because it does not exist.
At line:1 char:153
+ ... tulan\wt-A; Select-String -Path FINAL_REPORT.md -Pattern 'How to repr' -Context 0,40 | Select-Object -First 1 | ForEach-Object { $_.Context.PostContext }
+                 ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
    + CategoryInfo          : ObjectNotFound: (D:\Skill_tulan\wt-A\FINAL_REPORT.md:String) [Select-String], ObjectNotFoundException
    + FullyQualifiedErrorId : PathNotFound,Select-String
```

Đường tương đương: `README.md:46` (`python -m research.extract`) + `src/ardupilot_research_mcp/ingest/cli.py`
(`--all`, `--rebuild-index`) + `python -m research.build_params` + `python -m research.build_mavlink`.
Số liệu dùng để đối chiếu: `docs/blackbox/REPORT.md` §2.2(e) — 230 = 311 khối trong corpus − 52 khối bị
allowlist chặn − 25 khối cursor − 2 khối braced − 2 trùng tên.

## A-3. Phủ tham số (lỗi 3) — bước (1) test đang fail

`tests/test_param_coverage.py` (mới) chạy trên index hiện tại (params=230):

```
PS> python -m pytest tests/test_param_coverage.py -q
E           AssertionError: BATT_MONITOR
E           assert False is True

tests\test_param_coverage.py:96: AssertionError
=========================== short test summary info ============================
FAILED tests/test_param_coverage.py::test_group_prefix_resolves_the_full_parameter_name
FAILED tests/test_param_coverage.py::test_shared_suffix_does_not_return_another_groups_parameter
FAILED tests/test_param_coverage.py::test_index_status_publishes_the_parameter_count
FAILED tests/test_param_coverage.py::test_absent_names_are_not_invented_and_renames_come_from_the_pinned_notes
FAILED tests/test_param_coverage.py::test_real_frame_parameter_names_resolve_exactly
5 failed in 0.25s
```

Đo phủ trước khi sửa (`scripts/param_coverage.py`, output đầy đủ ở `docs/fix/A-coverage-before.txt`):

```
TOTAL (ArduCopter + libraries)      2859    2783
@Param blocks in directories the allowlist drops entirely: 2472
@Param blocks in scoped directories: 2783
params in index: 230
ratio params/@Param blocks: 8.26%
```

Khớp `docs/blackbox/REPORT.md` §2.2(e): 311 khối nằm trong corpus hiện tại = ArduCopter 142 +
AP_InertialSensor 105 + AP_GPS 45 + RC_Channel 10 + AP_Arming 9.

### Bước (2)(3) — sửa nguyên nhân gốc

Nguyên nhân: allowlist chỉ có 5 thư mục `libraries/`; corpus vì thế **không chứa file** khai báo
tham số của 96 thư mục còn lại. Ngoài ra `research/build_params.py` cũ **không ghép tiền tố**:
nó lưu nguyên hậu tố khai báo (`_OPTIONS`, `1_PROTOCOL`) nên `lookup_param` phải đoán bằng khớp
chuỗi đuôi, dẫn tới RC_OPTIONS trả cả ARMING_OPTIONS (báo cáo §2.2(b)) và SERIAL1_PROTOCOL /
BATT_FS_LOW_ACT không tìm được.

Sửa (đúng cơ chế của chính bản pin, `Tools/autotest/param_metadata/param_parse.py`): đi theo
chuỗi `@Group:`/`@Path:` từ `ArduCopter/Parameters.cpp` + `libraries/AP_Vehicle/AP_Vehicle.cpp`
(nhóm lồng nhau ghép tiếp tiền tố: `BATT` + `_` → `BATT_FS_LOW_ACT`; `SERIAL` + `1_PROTOCOL` →
`SERIAL1_PROTOCOL`). Khối không chuỗi nào tới được thì **không đoán**: không đưa vào bảng, liệt kê
 ở `docs/fix/A-unresolved.txt` (509 khối, kèm `file:dòng:tên (lý do)`).

`sources.yaml`: thêm 101 thư mục `libraries/*` có `@Param` (gồm bắt buộc AP_SerialManager,
AP_BattMonitor, AP_Vehicle; AP_Vehicle cần cho chuỗi tiền tố). Không sửa file ngoài write-scope.

```
PS> python -m research.extract --only ardupilot --force
ardupilot        files=5228      93.7MB license=COPYING.txt 7.2s
corpus total: 5228 files, 93.7MB

PS> python -m ardupilot_research_mcp.ingest.cli --source ardupilot
ardupilot        files=2448  chunks=20753  skipped=2652  filtered=59  binary=53  19.1MB 55.3s
counts: {"sources": 7, "documents": 7356, "chunks": 86262, "params": 230, "mavlink_msgs": 397, "mavlink_enums": 2367}

PS> python -m research.build_params --unresolved docs/fix/A-unresolved.txt
{"blocks": 2770, "stored_blocks": 2119, "rows": 5318, "unresolved_blocks": 509,
 "unlinked_blocks": 142, "params_in_table": 5089, "version": "Copter-4.7.2"}
```

Cổng A-3:

(i) `SERIAL1_PROTOCOL`, `BATT_FS_LOW_ACT` found:true bằng khớp **exact** (`tests/test_param_coverage.py`):

```
PS> python -m pytest tests/test_param_coverage.py -q
.....                                                                    [100%]
5 passed in 0.93s
```

(ii) Tên có thật từ 122 file `Tools/autotest/default_params/*.parm` + `Tools/Frame_params/*.param`
    tại pin (`scripts/param_coverage.py --names`, output đầy đủ `docs/fix/A-names.txt`):

```
names in 122 shipped parameter files: 1440
found by lookup_param: 739/1440 (51.3%)
not found: 701
```

Phân loại 701 tên không tìm thấy (đếm theo lý do do script in ra): phần lớn là tham số **của xe
khác** — các file `.param` đóng gói cả frame Plane/Rover/Sub/Blimp (ACRO_LOCKING, AIRSPEED_*,
ALT_SLOPE_*, Q_* …) mà bảng tham số ở đây là bảng **Copter** (chỉ đi chuỗi từ ArduCopter +
AP_Vehicle); phần còn lại là tên đã đổi (renamed_hint) hoặc cùng hậu tố khác tiền tố. Đây là
scope Copter chứ không phải lỗi ghép: mọi tên có trong bảng đều là khớp exact.

(iii) `index_status` công bố `counts.params` (sửa `query.index_status`) — test
`test_index_status_publishes_the_parameter_count` pass (cùng 5 passed ở trên).

(iv) Kích thước index: `(Get-Item data\index.sqlite).Length/1MB` → `183.47265625` (≤ 400 MB).

(v) `ARMING_CHECK`, `WPNAV_SPEED` vẫn found:false; ReleaseNotes tại pin có câu
    "ARMING_CHECK replaced with ARMING_SKIPCHK" (`ArduCopter/ReleaseNotes.txt:654`) nên trả
    `renamed_hint`, còn WPNAV_SPEED không có câu "replaced with" nên không gợi ý:

```
{"found": false, "query": "ARMING_CHECK", ...,
 "renamed_hint": {"old": "ARMING_CHECK", "new": "ARMING_SKIPCHK",
                  "path": "ArduCopter/ReleaseNotes.txt", "lines": [653, 660], ...},
 "note": "no parameter matched; nothing was invented; the pinned release notes record ARMING_CHECK replaced with ARMING_SKIPCHK"}
```

### Giải thích `params 230 → 5089` (bảng, không có bản ghi trùng nghĩa)

Output `docs/fix/A-params-rows.txt` (một dòng SQL mỗi câu):

```
rows: 5089
distinct param_name: 5089
distinct (path, line_start) blocks: 2070
distinct (path, line_start, prefix) groups: 5089
duplicate rows sharing (path, line_start, prefix): 0
blocks reached by more than one prefix: 550
rows per vehicle: [{'vehicle': 'shared', 'n': 4947}, {'vehicle': 'ArduCopter', 'n': 142}]
rows whose prefix carries an instance number: 2343
top prefixes by row count: SIM_ 227, OSD4_ 201, OSD3_ 201, OSD2_ 201, OSD1_ 201,
  (top-level "") 93, COMPASS_ 73, ATC_ 66, INS 62, CC2_ 42
rows whose param_name != prefix || name_raw: 0
```

5089 = 2070 khối `@Param` × các tiền tố mà **bảng Copter** gán cho khối đó. 550 khối được gán
nhiều tiền tố vì chúng là tham số **theo từng instance** của Copter (RC_Channel.cpp dưới `1_` …
`16_` → RC1_MIN..RC16_MIN; AP_OSD_Screen dưới `OSD1_`..`OSD5_`; AP_BattMonitor_Params dưới
`BATT_`, `BATT2_`..`BATTA_`; AP_InertialSensor dưới `INS`, `INS2_`, `INS3_`; SERIAL1..8; COMPASS2/3).
Đó là các tham số khác nhau của bản pin, không phải trùng nghĩa. **Không** có bản ghi trùng
`(path, dòng, tiền tố)` (0), mọi `param_name == prefix + name_raw` (0 sai), và không có bội
xe (chỉ Copter + shared) vì chuỗi chỉ đi từ bảng Copter.

### Thí nghiệm bị loại (bằng chứng "đã thử, không giữ hack")

**(a) Loại đường dẫn simulator khỏi allowlist** (lead cho phép thử MỘT lần; đã bỏ
`libraries/SITL/**`, re-extract, xoá 467 document SITL, rebuild FTS + params):

```
docs to drop: 467; counts documents=6889 chunks=82927
build_params: params_in_table=4642
pytest tests/test_query.py: 1 failed (test_out_of_corpus_question_is_not_answered)
golden: recall@5 = 30/30 = 1.000, precision@1 = 23/30 = 0.767, MRR = 0.859
```

P@1 về lại 0.767 nhưng test ngoài kho **vẫn fail** (nguyên nhân là comment "bread crumbs" trong
`libraries/AP_SmartRTL/AP_SmartRTL.cpp`, không thuộc SITL). Theo điều kiện lead đặt ra, đã
**revert**: thêm lại `libraries/SITL/**`, re-extract + ingest + build_params → params=5089,
index=183.5 MB. Hồi quy P@1 (0.733 so với 0.767) được liệt kê là known limitation, chờ nhánh C.

**(b) Ba biến thể guard trong `query.search` — đã ĐO rồi revert, không commit hack nào:**
  1. `unknown > known` (tỉ lệ từ không có trong index > 50%): query rác vẫn found:true
     ("bake"/"bread" có trong index, chỉ "sourdough" unknown = 1/3) → không hiệu quả.
  2. Candidate phải chứa ≥ một nửa số token: golden recall@5 tụt **29/30 = 0.967**, P@1 21/30.
  3. Candidate phải chứa **toàn bộ** token mà index biết: golden recall@5 tụt **26/30 = 0.867**,
     P@1 18/30. Ba lần đều revert; `query.py` chỉ còn thay đổi `counts.params`.

### Hồi quy còn lại của A-3 (known limitation, thuộc phạm vi C theo quyết định của lead)

```
PS> python -m pytest -q
1 failed, 84 passed in 24.05s
FAILED tests/test_query.py::test_out_of_corpus_question_is_not_answered   # "bread crumbs" trong AP_SmartRTL.cpp
PS> python scripts/fidelity_scan.py
TOTAL                          86262         0
fidelity: PASS
PS> python -m research.eval_retrieval --set tests/golden.yaml --aggregate-only
recall@5 = 30/30 = 1.000
precision@1 = 22/30 = 0.733   # G22 (ELRS packet rate) từ rank1 → rank3 vì libraries/SITL/SIM_ELRS.cpp
MRR = 0.837
```

Known limitation khác của bảng tham số (ghi rõ, không giả vờ đủ):
* tham số khai trong file `.lua` (AP_Scripting applets/drivers, 358 tên) không lấy — build_params
  chỉ đọc `.cpp/.h` như brief.
* tham số vector (`@Vector3Parameter` / field Vector3f) không tách `_X/_Y/_Z` như generator.
* file nguồn có dòng > 1000 ký tự bị ingest lọc (guard chống file sinh tự động) nên 142 khối
  `@Param` không có chunk → không có citation → không vào bảng (`unlinked_blocks=142`).
* 509 khối không ghép được tiền tố → liệt kê ở `A-unresolved.txt`, không đoán.

## A-1. Citation trỏ sai khối @Param (lỗi 1) — bước (1) test đang fail + CHẨN ĐOÁN trước khi sửa

`scripts/check_param_citations.py` (mới) kiểm từng hàng: (a) excerpt người gọi thấy có dòng
`@Param...: <hậu tố khai báo>`; (b) khoảng `lines` được cite bao dòng `line_start` của hàng;
(c) file nguồn tại khoảng dòng đó thật sự là khối ấy. Output TRƯỚC khi sửa
(`docs/fix/A-citations-before.txt`):

```
PS> python scripts/check_param_citations.py
params checked: 5089
citation violations: 3891
  ACRO_BAL_PITCH               ArduCopter/Parameters.cpp:307 lines=307-312 :: excerpt does not show the @Param line
  ACRO_OPTIONS                 ArduCopter/Parameters.cpp:805 lines=805-809 :: excerpt does not show the @Param line
  ...
```

### Chẩn đoán 5 tham số vi phạm (đo TRƯỚC khi sửa, output thô)

```
== FS_THR_ENABLE  path=ArduCopter/Parameters.cpp
   stored lines=124-128  real @Param line(s)=[124]  delta=[0]
   cited chunk lines=[95, 145]
   excerpt first line='    // @Param: FS_GCS_ENABLE'
== ARMING_SKIPCHK  path=libraries/AP_Arming/AP_Arming.cpp
   stored lines=195-198  real @Param line(s)=[195]  delta=[0]
   cited chunk lines=[178, 205]
   excerpt first line='    // @Param: CRSDP_IGN'
== BATT_FS_LOW_ACT  path=libraries/AP_BattMonitor/AP_BattMonitor_Params.cpp
   stored lines=143-145  real @Param line(s)=[143]  delta=[0]
   cited chunk lines=[134, 180]
   excerpt first line='    // @Param: CRT_MAH'
== RC_OPTIONS  path=libraries/RC_Channel/RC_Channels_VarInfo.h
   stored lines=92-96  real @Param line(s)=[92]  delta=[0]
   cited chunk lines=[84, 117]
   excerpt first line='    // @Param: _OVERRIDE_TIME'
== LOG_BITMASK  path=ArduCopter/Parameters.cpp
   stored lines=207-211  real @Param line(s)=[207]  delta=[0]
   cited chunk lines=[199, 232]
   excerpt first line='    // @Param: SIMPLE'
```

**Kết luận mẫu hình**: KHÔNG phải lệch dòng hằng số (delta = 0 cả 5 tham số; cả 3891 vi phạm
chỉ báo "excerpt does not show the @Param line", không có "stored line range is not this @Param
block" lẫn "cited lines ... do not cover"), KHÔNG phải chọn nhầm chunk khi khối vắt ngang hai
chunk (khối nằm nguyên vẹn trong chunk và lines bao đúng), KHÔNG phải trùng tên. Nguyên nhân:
`cite.build_citation` luôn trả **600 ký tự ĐẦU của chunk**, còn chunk code là khối 30-85 dòng
(~3000 ký tự), nên khối `@Param` nằm sâu trong chunk không xuất hiện trong excerpt — excerpt vì
thế hiển thị khối của tham số **trước đó** cùng chunk (FS_THR_ENABLE → FS_GCS_ENABLE;
ARMING_SKIPCHK → CRSDP_IGN; RC_OPTIONS → _OVERRIDE_TIME).

### Bước (1) test mới đang fail

```
PS> python -m pytest tests/test_param_citation_integrity.py -q
E       AssertionError: 3891 citations show another block: ['FHLD_XY_FILT_HZ (ArduCopter/mode_flowhold.cpp:34)', ...]
FAILED tests/test_param_citation_integrity.py::test_citation_excerpt_shows_the_parameter_block
FAILED tests/test_param_citation_integrity.py::test_citation_lines_cover_the_parameter_block
FAILED tests/test_param_citation_integrity.py::test_every_row_cites_its_own_param_line
3 failed in 0.72s
```

### Bước (2)(3) — sửa nguyên nhân gốc, chạy lại

Sửa:
1. `cite.build_param_citation()`: excerpt bắt đầu từ **dòng `@Param:` của chính tham số** (vẫn là
   lát cắt nguyên văn của chunk nên `verify_quote` giữ nguyên nghĩa), thay vì 600 ký tự đầu chunk.
   Dòng được tìm **theo nội dung** trong text của chunk, không cộng trừ số dòng: chunker
   `_slice()` strip các dòng trống đầu/cuối (`text = "\n".join(...).strip("\n")`) nên dòng thứ N
   của text không luôn là dòng `line_start + N` của file.
2. `research/build_params.link_chunk()`: neo vào chunk **chứa dòng `@Param:`** (chunk hẹp nhất),
   thay vì chunk bao khối metadata.
3. `lookup_param._row_out` và `decode_bitmask` dùng `build_param_citation`.

```
PS> python -m research.build_params --unresolved docs/fix/A-unresolved.txt
{"blocks": 2770, "stored_blocks": 2119, "rows": 5318, "unresolved_blocks": 509,
 "unlinked_blocks": 142, "params_in_table": 5089, "version": "Copter-4.7.2"}

PS> python scripts/check_param_citations.py
params checked: 5089
citation violations: 0
```
(trước sửa: 3891 vi phạm — file `docs/fix/A-citations-before.txt`; sau sửa: 0 — `A-citations-after.txt`)

Test đã pass:

```
PS> python -m pytest tests/test_param_citation_integrity.py -q
...                                                                      [100%]
3 passed in 1.59s
```

Ba cổng của bước (4):

```
PS> python -m pytest -q
1 failed, 87 passed in 26.04s
FAILED tests/test_query.py::test_out_of_corpus_question_is_not_answered   # known limitation A-3, scope C

PS> python scripts/fidelity_scan.py
TOTAL                          86262         0
fidelity: PASS

PS> python -m research.eval_retrieval --set tests/golden.yaml --aggregate-only
recall@5 = 30/30 = 1.000
precision@1 = 22/30 = 0.733
MRR = 0.837
```



