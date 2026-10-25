# Nhánh fix/C — lỗi 5 (glossary theo token + cờ ngoài phạm vi) và lỗi 7 (maxLength + che lỗi nội bộ)

Worktree: `D:\Skill_tulan\wt-C`, nhánh `fix/C`, base commit `7fe0382`.
Môi trường: `PYTHONPATH=src`, `ARM_REPO_ROOT=D:\Skill_tulan\wt-C`,
`GOVERNOR_HOME=D:\Skill_tulan\wt-C\research`, index riêng `data\index.sqlite` (bản sao).
Chỉ đọc `data/corpus` và `research/cache` (junction). Mọi lệnh chạy từ gốc worktree; output được
cắt bớt (trích ≤40 dòng, không cắt dòng FAIL/ERROR).

## 0. Baseline trước khi sửa (commit 7fe0382)

### 0.1 pytest
```
python -m pytest -q
........................................................................ [ 90%]
........                                                                 [100%]
80 passed in 24.97s
```

### 0.2 golden (dev set) + fidelity
```
python -m research.eval_retrieval --set tests/golden.yaml --aggregate-only
set=golden.yaml questions=30 k=5
recall@5 = 30/30 = 1.000
precision@1 = 23/30 = 0.767
MRR = 0.865
```
```
python scripts/fidelity_scan.py   (4 dòng cuối)
mavlink           markdown        19         0
----------------------------------------------
TOTAL                          65509         0
fidelity: PASS
```

## 1. Lỗi 5a — glossary khớp theo token

Hiện trạng (`src/ardupilot_research_mcp/query.py`, `expand_query`): `if vi in lowered` → khớp
chuỗi con, nên khoá `"bit"` khớp trong `"bitcoin"` (đúng case D4 của blackbox).

## 2. Lỗi 5 — Bước 1: test trước, chạy, chụp output fail

Test thêm vào `tests/test_query.py` (không sửa blackbox/golden/heldout):
- 9 câu tuyệt đối KHÔNG được mở rộng ("giá bitcoin hôm nay", "orbit height", "habit tracker",
  ...), 6 câu PHẢI mở rộng (token nguyên và cụm token liên tiếp).
- 6 câu tên sản phẩm ngoài kho, 2 câu phiên bản lạ, 1 câu phiên bản đang ghim (số phiên bản đọc
  từ bảng `sources`, không hardcode), 6 câu chủ đề không liên quan, 6 câu TRONG kho, và 1 test
  quét toàn bộ `tests/golden.yaml` đòi không câu nào bị gắn cờ.

```
python -m pytest tests/test_query.py -q -k "glossary or foreign or version or weak or in_scope or golden"
FAILED tests/test_query.py::test_glossary_does_not_match_a_fragment_of_a_word
FAILED tests/test_query.py::test_foreign_product_names_get_a_scope_note - Ass...
FAILED tests/test_query.py::test_unknown_version_is_flagged_with_the_pinned_labels
FAILED tests/test_query.py::test_pinned_version_is_not_flagged - KeyError: 's...
FAILED tests/test_query.py::test_unrelated_topics_get_a_weak_match_note - Ass...
FAILED tests/test_query.py::test_in_scope_questions_are_not_flagged - KeyErro...
FAILED tests/test_query.py::test_golden_questions_get_no_scope_note - KeyErro...
7 failed, 1 passed, 4 deselected in 0.92s
[exit code: 1]
```
File output đầy đủ: `docs/fix/C-5-prefix.txt`. Nguyên văn một assertion (thiếu khoá `scope_notes`):
```
>           assert payload["scope_notes"] == [], (question["id"], question["q"],
                   ^^^^^^^^^^^^^^^^^^^^^^
                                                 payload["scope_notes"])
E           KeyError: 'scope_notes'

tests\test_query.py:185: KeyError
```

## 3. Lỗi 5 — Bước 2+3: sửa nguyên nhân gốc

### 3.1 Thay đổi

`src/ardupilot_research_mcp/query.py`:
- `expand_query`: tách query và khoá từ điển bằng `TOKEN = re.compile(r"\w+", re.UNICODE)` rồi so
  khớp `_contains_phrase` (chuỗi token liên tiếp). Không còn `if vi in lowered`.
- `load_scope` đọc `scope.yaml` (dữ liệu, không hardcode trong `src/`).
- `scope_notes(query, results, labels=None, applied=None, con=None)` trả danh sách ghi chú:
  1. tên sản phẩm ngoài kho (khớp theo biên từ, không phân biệt hoa thường) → note
     "kho chỉ có tài liệu ArduPilot Copter đã ghim, ExpressLRS, EdgeTX, CRSF, MAVLink;
     không có <tên>";
  2. số phiên bản `X.Y`/`X.Y.Z` trong query không khớp bất kỳ nhãn nào đọc từ bảng `sources`
     (cột `version_label`, fallback `ref`) → note nêu các phiên bản đang ghim. Regex
     `VERSION = re.compile(r"(?<![\w.])(\d+\.\d+(?:\.\d+)?)(?!\w)")` — lookahead `(?!\w)` để
     "3.3V"/"2.4GHz" (số đo phần cứng) không bị coi là số phiên bản;
  3. khớp yếu: `_match_ratio` = tỉ lệ token nội dung (ASCII word + thuật ngữ glossary, bỏ
     stopword) của query xuất hiện theo biên từ trong path + heading_path + **toàn bộ text** của
     top-3 chunk (excerpt bị cắt 600 ký tự nên không đủ tin cậy) → dưới ngưỡng thì note
     "khớp yếu, có thể ngoài kho".
- `search()` gắn `scope_notes` và `confidence` (`"low"` nếu có note hoặc không có kết quả,
  `"high"` nếu sạch).

`scope.yaml` (mới): `out_of_scope_names: [PX4, Betaflight, iNav, Cleanflight, KISS,
QGroundControl]`. Đã đối chiếu index: `documents.path` chứa `qground` = 0 file; PX4/Betaflight/
iNav chỉ được *nhắc* trong tài liệu ArduPilot (18/2/3 file) chứ không có tài liệu của chúng.
Không đưa "Mission Planner" vào vì corpus có 28 tài liệu Mission Planner trong wiki ArduPilot.

### 3.2 Ngưỡng khớp yếu: 0.25 và lý do

Đo `_match_ratio` trên dev set `tests/golden.yaml` (30 câu, top-3 chunk đầy đủ):

| Tập | Giá trị đo | Kết luận |
|---|---|---|
| 30 câu golden (trong kho) | thấp nhất **0.33** (G08, G19); phần lớn 0.5-1.0 | ngưỡng phải ≤ 0.33 |
| câu ngoài kho không chung từ vựng ("giá ethereum hôm nay", "công thức nấu phở bò", "thời tiết Hà Nội ngày mai", "giá vàng hôm nay", "cách làm bánh mì", "đội hình bóng đá tối nay") | **0.00** (2 câu không có token nội dung ASCII → 0.0) | ngưỡng > 0.0 |

Chọn **0.25**: thấp hơn mức thấp nhất của golden (0.33) một khoảng an toàn, cao hơn các câu ngoài
kho không chung từ vựng (0.00). Không dùng case D1–D5 của blackbox để chọn ngưỡng.

**Hạn chế đã biết của ngưỡng:** heuristic là trùng từ vựng, nên câu ngoài kho *có chung từ* với
kho (ví dụ "how to train a puppy" 0.33-0.5 nhờ "train"/"pid"/"mission") không bị cờ khớp yếu;
chúng vẫn được xử lý bởi danh sách tên sản phẩm hoặc bởi `found:false` của FTS. Ghi nhận, không
nới ngưỡng để tránh gắn cờ nhầm câu trong kho.

### 3.3 Kết quả (output thô)

```
python -m pytest tests/test_query.py -q -k "glossary or foreign or version or weak or in_scope or golden"
........                                                                 [100%]
8 passed, 4 deselected in 4.06s
```
```
python -m pytest -q
........................................................................ [ 81%]
................                                                         [100%]
88 passed in 27.12s
```
```
python -m research.eval_retrieval --set tests/golden.yaml --aggregate-only
set=golden.yaml questions=30 k=5
recall@5 = 30/30 = 1.000
precision@1 = 23/30 = 0.767
MRR = 0.865
```
```
python scripts/fidelity_scan.py   (2 dòng cuối)
TOTAL                          65509         0
fidelity: PASS
```
Không hồi quy: golden recall@5 giữ 1.000, P@1 giữ 0.767, MRR giữ 0.865, test cũ 80/80 pass.

## 4. Known limitation của lỗi 5 (KHÔNG sửa xếp hạng)

Theo brief, không chỉnh ranking để cứu các case C của blackbox; chúng được ghi nhận là hạn chế:
- **C4** (query kiểu "where does ArduPilot parse CRSF"): tài liệu/wiki đứng trên code ArduPilot vì
  BM25 không ưu tiên đúng file code khi câu hỏi có nhiều từ chung.
- **C10** (query kiểu "SERIAL port protocol RC input"): top-5 thiếu trang tham số SERIALx_/
  AP_RCProtocol tương ứng — lỗ hổng phủ index/ranking, không phải lỗi glossary.
- **C11** (query kiểu "EdgeTX CRSF telemetry"): kết quả nghiêng về code CRSF chung thay vì file
  EdgeTX; thứ hạng theo BM25, không sửa.
Cả ba không bị ảnh hưởng bởi thay đổi lỗi 5 (không có glossary key, không có tên/phiên bản ngoài
kho, `_match_ratio` của chúng cao nên không bị gắn cờ).

## 5. Lỗi 7 — Bước 1: test trước, chạy, chụp output fail

Test thêm vào `tests/test_query.py`: query 1 MB, 100 KB, đúng ngưỡng 2000, vượt 1 ký tự; validate
trước khi chạm SQL (monkeypatch `_base.db.connect` ném lỗi nếu bị gọi); che lỗi nội bộ
(monkeypatch `ardupilot_research_mcp.query.search` ném
`sqlite3.OperationalError("LIKE or GLOB pattern too complex")`, đòi payload không chứa
"sqlite"/"LIKE"/"GLOB"/"OperationalError" và `error_id` xuất hiện trên stderr); giới hạn của
`get_chunk.cite_id`, `lookup_param.name_or_pattern`, `parse_ihex_summary.path`,
`check_intelhex_line.line`; schema `tools/list` phải khai `maxLength`.

```
python -m pytest tests/test_query.py -q -k "limit or huge or masked or tools_apply or schemas"
>       assert schema["properties"]["query"]["maxLength"] == QUERY_LIMIT
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
E       KeyError: 'maxLength'

tests\test_query.py:266: KeyError
=========================== short test summary info ============================
FAILED tests/test_query.py::test_query_length_limit_is_checked_before_sql - A...
FAILED tests/test_query.py::test_huge_query_is_refused_without_a_sql_error[100000]
FAILED tests/test_query.py::test_huge_query_is_refused_without_a_sql_error[1000000]
FAILED tests/test_query.py::test_unexpected_search_error_is_masked_and_logged
FAILED tests/test_query.py::test_other_tools_apply_their_limits[<lambda>-cite_id too long (max 128 chars)]
FAILED tests/test_query.py::test_other_tools_apply_their_limits[<lambda>-name_or_pattern too long (max 128 chars)]
FAILED tests/test_query.py::test_other_tools_apply_their_limits[<lambda>-path too long (max 1024 chars)]
FAILED tests/test_query.py::test_other_tools_apply_their_limits[<lambda>-line too long (max 600 chars)]
FAILED tests/test_query.py::test_tool_schemas_advertise_max_length - KeyError...
9 failed, 1 passed, 12 deselected in 1.91s
[exit code: 1]
```
File output đầy đủ: `docs/fix/C-7-prefix.txt`.

## 6. Lỗi 7 — Bước 2+3: sửa nguyên nhân gốc

### 6.1 Thay đổi (`src/ardupilot_research_mcp/tools/_base.py`)

- `LIMITS`: bảng giới hạn ký tự cho **mọi** tham số chuỗi tự do của mọi tool (trừ
  `decode_crsf_frame` — nhánh D sở hữu schema tool đó; tool này cũng không có `maxLength` trong
  tools/list, xem 6.4).
- `_signatures`: gắn `Annotated[..., MaxLen(n)]` vào chữ ký công khai → `maxLength` xuất hiện
  trong JSON schema của tools/list. `MaxLen.__get_pydantic_json_schema__` chỉ **quảng cáo**
  giới hạn, không tạo pydantic constraint; nếu để pydantic chặn thì SDK trả lỗi protocol
  (`pydantic ValidationError: String should have at most N characters` → `ToolError`) trước khi
  tool chạy, phá vỡ hợp đồng `{"found": false, ...}`. Đã kiểm chứng nguyên văn traceback đó khi
  thử `StringConstraints(max_length=5)` + query 10 ký tự qua `mcp.call_tool`:
  `pydantic_core._pydantic_core.ValidationError: 1 validation error for t1Arguments / String
  should have at most 5 characters [type=string_too_long]` → `ToolError: Error executing tool
  t1`. Vì vậy giới hạn được **validate trong wrapper** (`_too_long`) trước khi mở index.
- `_too_long`: bind tham số vào chữ ký đầy đủ rồi so `len(value) > limit`; trả
  `{"found": false, "error": "<tên> too long (max N chars)", "max_length": N}`.
- `guarded`/`guarded_pure`: bọc `except Exception` → `_internal_error`: trả
  `{"found": false, "error": "internal error", "error_id": "<8 hex>"}`, in `repr(exc)` +
  traceback ra stderr kèm cùng `error_id`. `SlowDown` của rate-guard vẫn ném ra ngoài
  (`GUARD.check()` đứng trước khối try) và `KeyError`/`ValueError` vẫn giữ thông điệp cũ.

Bảng giới hạn (lý do: độ dài thực tế của dữ liệu trong index):

| tool | tham số | maxLength | lý do |
|---|---|---|---|
| search_docs | query | 2000 | câu hỏi tự do; câu dài nhất trong golden 43 ký tự, 2000 đủ cho cả đoạn văn dán vào |
| search_docs | scope | 32 | enum: "protocol" dài nhất 8 |
| search_docs | version | 128 | nhãn pin dài nhất "wiki@828de1f (2026-10-24)" = 26 |
| search_docs | tier_max | 8 | enum T1/T2/T3 |
| get_chunk | cite_id | 128 | dạng `<source>#<16 hex>` ≤ ~30 ký tự |
| lookup_param | name_or_pattern | 128 | tên tham số dài nhất trong `params` = 15 ký tự |
| lookup_param | vehicle, version | 64, 128 | tên xe; nhãn pin |
| decode_bitmask | param | 128 | như trên |
| decode_bitmask | value | 1024 | danh sách tên bit phân tách bằng dấu phẩy; khối @Bitmask dài nhất 804 ký tự |
| decode_bitmask | vehicle, version | 64, 128 | tên xe; nhãn pin |
| find_source | symbol_or_file | 1024 | có thể là đường dẫn repo (đường dẫn index dài nhất 116) |
| find_source | repo, version | 64, 128 | source id; nhãn pin |
| board_info | board_name, hal | 128, 64 | tên board (vd CubeOrangePlus); HAL (ChibiOS/ESP32) |
| mavlink_message | name_or_id | 128 | tên message/enum |
| troubleshoot | symptom, context | 2000, 2000 | câu hỏi tự do |
| get_script | topic | 128 | tên chủ đề |
| parse_ihex_summary | path | 1024 | đường dẫn file trong data/ |
| check_intelhex_line | line | 600 | một bản ghi Intel HEX = 43 ký tự; 600 cho ~13 bản ghi liền nhau |
| index_status, list_sources | — | — | không có tham số chuỗi |
| decode_crsf_frame | hex | (không đặt ở nhánh C) | nhánh D sở hữu schema/tool này |

### 6.2 Bằng chứng schema tools/list

```
python - (import ardupilot_research_mcp.server, in tools/list của mcp._tool_manager)
search_docs          {'query': 2000, 'scope': 32, 'version': 128, 'tier_max': 8}
get_chunk            {'cite_id': 128}
lookup_param         {'name_or_pattern': 128, 'vehicle': 64, 'version': 128}
decode_bitmask       {'param': 128, 'value': 1024, 'vehicle': 64, 'version': 128}
find_source          {'symbol_or_file': 1024, 'repo': 64, 'version': 128}
board_info           {'board_name': 128, 'hal': 64}
mavlink_message      {'name_or_id': 128}
troubleshoot         {'symptom': 2000, 'context': 2000}
get_script           {'topic': 128}
decode_crsf_frame    {}
check_intelhex_line  {'line': 600}
parse_ihex_summary   {'path': 1024}
list_sources         {}
index_status         {}
```

### 6.3 Kết quả (output thô)

```
python -m pytest tests/test_query.py -q
......................                                                   [100%]
22 passed in 5.51s
```
```
python -m pytest -q
........................................................................ [ 73%]
..........................                                               [100%]
98 passed in 28.69s
```
```
python -m research.eval_retrieval --set tests/golden.yaml --aggregate-only
set=golden.yaml questions=30 k=5
recall@5 = 30/30 = 1.000
precision@1 = 23/30 = 0.767
MRR = 0.865
```
```
python scripts/fidelity_scan.py   (2 dòng cuối)
TOTAL                          65509         0
fidelity: PASS
```

## 7. Việc không chạy được trong sandbox của teammate

`scripts/tool_matrix.py` (kiểm thủ tục E2E qua stdio) **không chạy được** trong phiên này vì
sandbox chặn tạo pipe cho subprocess — nguyên văn:
```
  File "C:\Users\ADMIN\AppData\Local\Programs\Python\Python311\Lib\asyncio\windows_utils.py", line 63, in pipe
    h2 = _winapi.CreateFile(
PermissionError: [WinError 5] Access is denied
[sandbox: file access denied under workspace-write mode]
[exit code: 1]
```
Không thử cách khác (theo chỉ dẫn: sandbox chặn pipe thì dán lỗi và dừng). Bù lại, schema của
cả 14 tool đã được sinh trực tiếp qua `mcp._tool_manager` (mục 6.2) và toàn bộ test unit pass.
Kiểm E2E qua stdio (tool_matrix, blackbox) cần chạy ở phiên không bị chặn pipe.



