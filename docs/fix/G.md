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
