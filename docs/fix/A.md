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
