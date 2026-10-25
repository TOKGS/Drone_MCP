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
