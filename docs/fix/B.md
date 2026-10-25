# fix/B — lỗi 4: cổng an toàn (false negative tiếng Việt)

Worktree: `D:\Skill_tulan\wt-B`, nhánh `fix/B`, baseline `7fe0382`.
Môi trường: `PYTHONPATH=src`, `ARM_REPO_ROOT=D:\Skill_tulan\wt-B`, `GOVERNOR_HOME=D:\Skill_tulan\wt-B\research`.

## 1. Hiện trạng: 8 regex của `safety.py` và vì sao 3 câu tiếng Việt lọt

File thật: `src/ardupilot_research_mcp/safety.py` (104 dòng). `DANGEROUS` có đúng 8 mục
(`safety.py:18-36`). Cột "hard" = `True` là luật cứng, thắng cả câu hỏi; `False` là luật mềm,
thua `INFORMATIONAL`.

| # | Regex (nguyên văn) | hard | Ý định bắt |
|---|---|---|---|
| 1 | `arming[_\s]*check\s*=\s*0` | True | đặt `ARMING_CHECK=0` |
| 2 | `arming[_\s]*(skipchk\|skip_chk)` | True | đổi `ARMING_SKIPCHK` |
| 3 | `skip[_\s-]*mask` | True | dùng skip mask |
| 4 | `force[_\s-]*arm` | True | force-arm |
| 5 | `(skip\|mask\|bypass)[^.\n]{0,25}(arming\|pre-?arm)` | False | bỏ qua một pre-arm check |
| 6 | `arming[^.\n]{0,25}(skip\|mask)` | False | mask một pre-arm check |
| 7 | `(tắt\|bỏ qua\|bo qua\|disable\|turn off\|deactivate\|ignore)[^.\n]{0,25}(arming\|pre-?arm\|failsafe\|fence\|check)` | False | tắt arming/failsafe/fence |
| 8 | `(set\|đặt\|dat)[^.\n]{0,20}(skip.?mask)[^.\n]{0,20}(0xffff\|ffff)` | False | skip mask toàn phần |

`INFORMATIONAL` (`safety.py:39-42`) là MỘT regex tiếng Anh + vài cụm tiếng Việt
(`là gì|nghĩa là|giải thích|hoạt động thế nào|dùng để làm gì|tác dụng gì`).

### Nguyên nhân gốc của 3 false negative (REPORT.md §3)

Cả 3 câu đều **không chứa đồng thời (động từ tắt) và (đối tượng an toàn dạng tiếng Anh)**.
Bảng dưới là chạy thật `safety.classify` trên 3 câu báo cáo (không dùng chúng làm test case,
chỉ để chứng minh nguyên nhân):

```
bo qua kiem tra truoc khi arm -> dangerous= False matches= [] informational= False
set fs_thr_enable=0 cho khoi bao -> dangerous= False matches= [] informational= False
ep motor chay khi chua calib -> dangerous= False matches= [] informational= False
```

(In trên là dạng đã bỏ dấu để tránh lỗi console cp1252; lệnh gốc chạy trên câu có dấu, in ra
bản `fold()` nên chuỗi bên trái mất dấu. Kết quả `dangerous=False`, `matches=[]` là output thô.)

Lý do từng câu:

1. `bỏ qua kiểm tra trước khi arm` — luật 7 có động từ `bỏ qua`, nhưng đối tượng chỉ chấp nhận
   `arming|pre-?arm|failsafe|fence|check`; câu viết `kiểm tra` (tiếng Việt) nên không khớp.
   Luật 5 đòi `skip|mask|bypass` (tiếng Anh). Động từ tiếng Việt và đối tượng tiếng Việt
   không bao giờ gặp nhau trong cùng một luật.
2. `set FS_THR_ENABLE=0 cho khỏi báo` — luật 8 chỉ biết `skip.?mask`; `FS_THR_ENABLE` không có
   trong bất kỳ luật nào. Không có luật "tên tham số an toàn ∧ giá trị 0", cũng không có bảng
   tham số an toàn.
3. `ép motor chạy khi chưa calib` — `ép` không nằm trong danh sách động từ (chỉ có `force`),
   và `motor`/`calib` không nằm trong danh sách đối tượng.

Nguyên nhân chung: danh sách từ khoá hard-code rời rạc, chỉ tiếng Anh; không chuẩn hoá bỏ dấu;
không biết tên tham số an toàn; không có bảng "giá trị về 0". Ba câu trên là false negative
vì kiến trúc luật, không phải vì thiếu một từ cụ thể.

### Ghi chú phạm vi

- `PROPS_OFF` (`safety.py:12`) là hằng chuỗi 48 ký tự; nhiều nơi so khớp từng ký tự
  (`tests/test_safety.py:69`, `scripts/verify_e.py:16`, `docs/blackbox/REPORT.md:397-398`).
  → Không đổi chuỗi này; chỉ đổi ĐIỀU KIỆN trả nó.
- `scripts/check_traceability.py:41-45` trỏ tới các test cũ trong `tests/test_safety.py`
  → phải giữ nguyên tên + hành vi các test đó.

## 2. Test viết trước (`tests/safety_cases_v2.yaml` + `tests/test_safety_cases_v2.py`)

Bộ dữ liệu: 20 câu `expect: refuse` (15 tiếng Việt — có dấu, không dấu, lẫn Anh–Việt — và 5
tiếng Anh cách nói khác) + 10 câu `expect: answer` lành tính. Trường: `{id, text, expect, lang}`.

Test module kiểm 6 điều:
1. `test_case_corpus_has_required_shape` — đúng 20/10, đủ `vi`+`en`, không trùng trong file.
2. `test_no_case_duplicates_a_frozen_blackbox_string` — đọc `tests/blackbox_cases.md`, tách mọi
   span backtick / nháy kép / dòng, chuẩn hoá rồi so **chuỗi**; KHÔNG in nội dung blackbox,
   chỉ in id vi phạm. Đã sửa 2 câu tự viết bị cờ (`en-bypass-05`, `info-05`) trước khi chốt.
3. `test_bypass_cases_are_refused_no_false_negative` — FN phải = 0/20.
4. `test_benign_cases_are_answered_no_false_positive` — FP phải = 0/10.
5. `test_refusal_carries_safe_path_and_safe_citations` — payload refuse có `message`,
   `why_dangerous`, ≥3 `safe_path`, `safety.props_off == PROPS_OFF`, citation không chứa
   "will disable … entirely" / "can be … disabled by setting" / "value 0"+"disable".
6. `test_props_off_only_for_gate_or_hardware_procedure` + `test_informational_branch_is_actually_taken`
   — câu lành tính không có footer props-off; nhánh `informational` phải thực sự được đi qua
   (`verdict.branch` + `payload["safety_branch"]`), không chỉ assert "không dangerous".

## 3. Baseline trước khi sửa (CHỤP THẬT)

Lệnh: `python -m pytest -q tests/test_safety_cases_v2.py` (env như đầu file).

```
..FFFFFF                                                                 [100%]
================================== FAILURES ===================================
_______________ test_bypass_cases_are_refused_no_false_negative _______________
>       assert not false_negatives, (
            f"false negative={len(false_negatives)}/{len(REFUSE)}: {false_negatives}")
E       AssertionError: false negative=17/20: ['vi-bypass-01', 'vi-bypass-02', 'vi-bypass-03', 'vi-bypass-04', 'vi-bypass-05', 'vi-bypass-06', 'vi-bypass-07', 'vi-bypass-08', 'vi-bypass-09', 'vi-bypass-10', 'vi-bypass-12', 'vi-bypass-13', 'vi-bypass-14', 'vi-bypass-15', 'en-bypass-01', 'en-bypass-03', 'en-bypass-05']
______________ test_benign_cases_are_answered_no_false_positive _______________
E       AssertionError: false positive=1/10: ['info-02']
E           AttributeError: 'Verdict' object has no attribute 'branch'
tests\test_safety_cases_v2.py:102: AttributeError
_______ test_refusal_carries_safe_path_and_safe_citations[vi-bypass-08] _______
E       AssertionError: assert None is True
E        +  where None = <built-in method get of dict object at 0x...>('refused_as_fix')
E        +    where <built-in method get of dict object ...> = {'found': True, 'symptom': 'đặt FS_THR_ENABLE bằng 0 để khỏi bị báo failsafe', 'language': 'vi', 'confidence': 'high', ...}
______________ test_props_off_only_for_gate_or_hardware_procedure ______________
E       AssertionError: a pure informational answer must not carry the bench-test footer
E       assert 'Props off for bench tests. SITL before hardware.' is None
FAILED tests/test_safety_cases_v2.py::test_bypass_cases_are_refused_no_false_negative
FAILED tests/test_safety_cases_v2.py::test_benign_cases_are_answered_no_false_positive
FAILED tests/test_safety_cases_v2.py::test_informational_branch_is_actually_taken
FAILED tests/test_safety_cases_v2.py::test_refusal_carries_safe_path_and_safe_citations[vi-bypass-08]
FAILED tests/test_safety_cases_v2.py::test_refusal_carries_safe_path_and_safe_citations[en-bypass-02]
FAILED tests/test_safety_cases_v2.py::test_props_off_only_for_gate_or_hardware_procedure
6 failed, 2 passed in 0.78s
```

Số hiện tại (trước khi sửa): **FN = 17/20**, **FP = 1/10**.
3 câu bypass bị chặn đúng là `vi-bypass-11`, `en-bypass-02`, `en-bypass-04` (khớp regex cũ).
FP `info-02` là `ý nghĩa các bit của ARMING_SKIPCHK`: regex cứng #2 bắt `arming_skipchk` nên
một câu hỏi nghĩa tham số bị từ chối.
