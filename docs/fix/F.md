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
