# Nhánh fix/F — 2 hồi quy sau khi merge A (cổng "không có neo trong kho" + hạ hạng code SITL)

Worktree `D:\Skill_tulan\wt-C`, nhánh `fix/F` cắt từ `master` (`e444d27`, đã merge `fix/A f169cd5`).
Index mới của nhánh A: 183,5 MB, `params 5089`, `chunks 86262`, `documents 7356`, Copter-4.7.2.
KHÔNG rebuild index. `data/corpus` là junction chỉ đọc. Mọi lệnh chạy từ gốc worktree với
`PYTHONPATH=src`; output cắt bớt (≤40 dòng, không cắt dòng FAIL/ERROR/Traceback).

## 0. Baseline trên master + A (đo lại, khớp số lead đưa)

```
python -m pytest -q
E           assert True is False
tests\test_query.py:44: AssertionError
FAILED tests/test_query.py::test_out_of_corpus_question_is_not_answered - ass...
1 failed, 127 passed in 37.91s
```
```
python -m research.eval_retrieval --set tests/golden.yaml --aggregate-only
set=golden.yaml questions=30 k=5
recall@5 = 30/30 = 1.000
precision@1 = 22/30 = 0.733
MRR = 0.837
```
```
python -m research.eval_retrieval --set tests/heldout_v3.yaml --aggregate-only
set=heldout_v3.yaml questions=30 k=5
recall@5 = 28/30 = 0.933
precision@1 = 25/30 = 0.833
MRR = 0.868
```
```
python scripts/fidelity_scan.py   (2 dòng cuối)
TOTAL                          86262         0
fidelity: PASS
```
Log đầy đủ: `docs/fix/F-baseline.txt`.

## 1. F-1 — Bước 1: test trước, chụp output fail

Test thêm vào `tests/test_query.py` (không sửa blackbox/golden/heldout/conftest): 7 câu không
liên quan phải trả `found:false` + `results:[]` + `candidates:[]` + note nói ngoài phạm vi +
`confidence:low`; 8 câu trong kho phải vẫn trả lời; và toàn bộ `tests/golden.yaml` phải
`found:true` (không câu nào bị cổng neo chặn).

```
python -m pytest tests/test_query.py -q -k "anchor"
________________ test_query_without_a_corpus_anchor_is_refused ________________

    def test_query_without_a_corpus_anchor_is_refused(con) -> None:
        for text in NO_ANCHOR_QUERIES:
            payload = query.search(con, text, limit=5)
>           assert payload["found"] is False, (text, [item["path"] for item in payload["results"]])
E           AssertionError: ('how do I bake sourdough bread', ['libraries/AP_Scripting/applets/arming-checks.lua', 'libraries/AP_SmartRTL/AP_SmartRTL.cpp'])
E           assert True is False

tests\test_query.py:297: AssertionError
=========================== short test summary info ============================
FAILED tests/test_query.py::test_query_without_a_corpus_anchor_is_refused - A...
1 failed, 2 passed, 22 deselected in 3.48s
[exit code: 1]
```
File output đầy đủ: `docs/fix/F-1-prefix.txt`.

## 2. F-1 — Bước 2+3: cổng "không có neo trong kho"

### 2.1 Cách làm (tổng quát, không hardcode file/câu hỏi)

`src/ardupilot_research_mcp/query.py`:
- `_document_frequency(con, token)`: số document chứa token qua FTS5, **cắt ở 3** (subquery
  `SELECT DISTINCT d.id ... LIMIT 3`) nên rẻ.
- `_corpus_anchor(con, query, applied)`: lấy token nội dung (`_content_tokens`: từ ASCII của câu
  + thuật ngữ glossary, bỏ stopword) rồi tính trọng số:
  - `+1.0` nếu token xuất hiện trong **>= 3 document**, hoặc là **ký hiệu code** (chứa `_`) và
    xuất hiện ít nhất 1 document;
  - `+0.25` nếu là từ tự nhiên chỉ xuất hiện ở 1-2 document (nhiễu: comment lẻ, applet);
  - `+0.0` nếu không có trong index.
- Cổng: `weight < 1.0` **hoặc** `weight / len(content) < 0.5` → trả
  `found:false`, `results:[]`, `candidates:[]`, `confidence:"low"`, note
  `query has no anchor in the indexed corpus: ... -> out of scope; nothing was invented`.
  `scope:local` được miễn (overlay file người dùng cố ý nhỏ, không cần từ vựng corpus).

Vì sao không dùng ngưỡng đơn giản hơn: token 2 chữ cái sinh ra từ tiếng Việt có dấu
(`th`, `ng`, `ti`...) có df cao một cách vô nghĩa; `_content_tokens` bỏ chúng (từ Unicode đầy đủ,
không phải mảnh ASCII) nên phép đo mới tách được câu ngoài kho.

### 2.2 Số đo chọn ngưỡng (chạy trước khi sửa, trên index mới)

| Tập | Kết quả đo |
|---|---|
| `tests/golden.yaml` (30 câu) | weight/ratio thấp nhất **0.50** (G14 "vì sao không arm được?": `arm` df>=3, `sao` df=0); 29/30 câu ratio >= 0.67; **0 câu** bị cổng chặn (test `test_golden_questions_keep_a_corpus_anchor` pass) |
| `tests/heldout_v3.yaml` (30 câu) | **0 câu** bị chặn; recall@5 giữ nguyên 28/30 = 0.933. V3-12 "Giải thích rtun_str_i_ratio." có 1 token df thấp nhưng là ký hiệu code (`_`) nên weight 1.0 → không bị chặn |
| ngoài kho | `how do I bake sourdough bread` (bake=1, bread=1, sourdough=0 → weight 0.50, ratio 0.17), `how do I bake bread` (0.50/0.25), `giá ethereum hôm nay` (0.0), `thời tiết Hà Nội ngày mai` (0.25), `công thức nấu phở bò` (0.0, không token nội dung), `best pizza dough recipe` (1.0/0.25), `how to knit a wool scarf` (0.0) → **bị chặn hết** |

Hạn chế đã biết: câu ngoài kho mà **trùng từ vựng** với corpus ("habit tracker app review":
app/tracker/review đều df cao) vẫn qua cổng neo — đây là giới hạn của phép đo từ vựng, ghi nhận
không nới ngưỡng (nới sẽ chặn nhầm câu trong kho như G14 ratio 0.50).

Ghi chú: `test_unrelated_topics_get_a_weak_match_note` (của fix/C) được đổi thành
`test_unrelated_topics_are_refused_not_weakly_answered` vì hành vi mới **chặt hơn**: các câu đó
giờ `found:false` thay vì `found:true` + note "khớp yếu".

### 2.3 Kết quả (output thô)

```
python -m pytest tests/test_query.py -q -k "anchor"
...                                                                      [100%]
3 passed, 22 deselected in 3.86s
```
```
python -m pytest tests/test_query.py::test_out_of_corpus_question_is_not_answered -q
.                                                                        [100%]
1 passed in 0.09s
```
```
python -m pytest -q
........................................................................ [ 54%]
...........................................................              [100%]
131 passed in 39.42s
```
```
python -m research.eval_retrieval --set tests/golden.yaml --aggregate-only
set=golden.yaml questions=30 k=5
recall@5 = 30/30 = 1.000
precision@1 = 22/30 = 0.733
MRR = 0.837
```
```
python scripts/fidelity_scan.py   (2 dòng cuối)
TOTAL                          86262         0
fidelity: PASS
```
Log đầy đủ: `docs/fix/F-1-green.txt`. P@1 vẫn 0.733 (hồi quy còn lại của F-2, chưa sửa ở bước này).

## 3. F-2 — Bước 1: test trước, chụp output fail

Test thêm vào `tests/test_query.py`:
- `test_simulator_code_does_not_win_the_top_spot`: 2 câu mà code `libraries/SITL/` đang chiếm top-1
  ("ELRS packet rate đọc ở đâu?", "how does the buzzer work") — top-1 không được nằm dưới
  `libraries/SITL/`.
- `test_golden_precision_and_recall_hold`: tự tính recall@5 / precision@1 trên `tests/golden.yaml`
  bằng chính `research.eval_retrieval.is_hit`, đòi recall 30/30 và P@1 >= 0.767.

```
python -m pytest tests/test_query.py -q -k "simulator or golden_precision"
    assert recall == len(questions), f"recall@5 = {recall}/{len(questions)}"
>   assert precision / len(questions) >= 0.767, f"precision@1 = {precision}/{len(questions)}"
E   AssertionError: precision@1 = 22/30
E   assert (22 / 30) >= 0.767

tests\test_query.py:354: AssertionError
=========================== short test summary info ============================
FAILED tests/test_query.py::test_simulator_code_does_not_win_the_top_spot - A...
FAILED tests/test_query.py::test_golden_precision_and_recall_hold - Assertion...
2 failed, 25 deselected in 3.19s
```
File output đầy đủ: `docs/fix/F-2-prefix.txt`.


