# Nhật ký nhánh fix/G — integrity test FAIL khi corpus (gitignored) vắng mặt

Worktree `D:\Skill_tulan\wt-A`, nhánh `fix/G` từ `master` (base `84e3598`). Ngân sách ~25 bước.

## Bối cảnh (bằng chứng thô từ lead, clone công khai + copy index, KHÔNG extract corpus)

```
$env:PYTHONPATH='src'; python -m pytest -q
→ 1 failed, 132 passed in 41.66s
FAILED tests/test_param_citation_integrity.py::test_citation_lines_cover_the_parameter_block
FileNotFoundError: [Errno 2] No such file or directory:
  'D:\\Skill_tulan\\drone-mcp-verify\\data\\corpus\\ardupilot\\ArduCopter\\Parameters.cpp'
```

`data/corpus/` bị `.gitignore`; `tests/test_param_citation_integrity.py` skip theo index/params
(có), nhưng `source_lines()` đọc thẳng `config.corpus_root()/ardupilot/<path>` mà không kiểm tra
corpus có tồn tại — nên trên clone mới test **fail** thay vì **skip**.

## Bước (1) — test mới, đang fail

Thêm `test_source_check_skips_when_the_corpus_is_absent`: monkeypatch `config.corpus_root()` sang
thư mục rỗng rồi gọi thẳng `test_citation_lines_cover_the_parameter_block()`, kỳ vọng nó
`pytest.skip` chứ không đọc file.

```
PS> python -m pytest tests/test_param_citation_integrity.py -q
>       return io.open(self, mode, buffering, encoding, errors, newline)
E       FileNotFoundError: [Errno 2] No such file or directory: '...\\corpus\\ardupilot\\ArduCopter\\Parameters.cpp'
FAILED tests/test_param_citation_integrity.py::test_source_check_skips_when_the_corpus_is_absent
1 failed, 3 passed in 2.49s
```

## Bước (2) — sửa tối thiểu

* `corpus_file(row)` (mới): trả `Path` của file nguồn, hoặc `None` khi `data/corpus/` chưa được
  extract (`path.is_file()` sai) — dùng chung một chỗ.
* `source_lines(row)`: dùng `corpus_file()`; nếu `None` thì
  `pytest.skip("corpus not extracted: run python -m research.extract")`.
* Không nới lỏng khẳng định nào khi corpus CÓ mặt: vẫn kiểm excerpt chứa `@Param:<hậu tố>` và
  `lines` bao `line_start` cho **mọi** dòng trong bảng (test 3 chạy toàn bộ bảng, không đổi).
* Test mới tăng thêm một khẳng định: `corpus_file({"path": "ArduCopter/Parameters.cpp"}) is None`
  khi corpus trỏ vào thư mục rỗng.

## Bước (3) — chứng minh cả hai chiều

### (a) Trong `wt-A`, corpus đầy đủ — chạy thật, KHÔNG skip

```
PS> python -m pytest tests/test_param_citation_integrity.py -q -rs
....                                                                     [100%]
4 passed in 1.93s
```

### (b) Tạm đổi tên `data\corpus` → `corpus.bak` — phải SKIP, không fail

```
PS> Rename-Item data\corpus corpus.bak
PS> python -m pytest tests/test_param_citation_integrity.py -q -rs
.s..                                                                     [100%]
=========================== short test summary info ============================
SKIPPED [1] tests\test_param_citation_integrity.py:50: corpus not extracted: run python -m research.extract
3 passed, 1 skipped in 1.96s
PS> Rename-Item data\corpus.bak corpus      # đã đổi tên lại (Test-Path data\corpus → True)
```

### (c) Toàn bộ suite + fidelity trong `wt-A` (corpus đã đổi tên lại trước khi chạy fidelity)

```
PS> python -m pytest -q
134 passed in 41.56s

PS> python scripts/fidelity_scan.py
TOTAL                          86262         0
fidelity: PASS
```

Kết luận: trên clone mới không có `data/corpus`, bộ test integrity chuyển từ **fail** sang
**skip** kèm hướng dẫn chạy `research.extract`; khi corpus có mặt, mọi khẳng định cũ vẫn chạy đủ
(134 passed, 0 skipped ở nhánh bình thường).
