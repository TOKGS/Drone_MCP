# Run2 — kiểm tra tính tất định của 5 script chấm điểm

Bối cảnh: verifier độc lập (`verify-run2`) chấm run2 bằng 5 script, mỗi script **một lần**. Người
dùng yêu cầu chạy lại lần 2 để biết kết quả có tất định hay không. Đây là phép đo đó (lead chạy,
cùng máy, cùng `docs/blackbox/raw` của run2 trong worktree `D:\Skill_tulan\bb-run2`).

## Cách chạy

```powershell
cd D:\Skill_tulan\bb-run2          # worktree cách ly chứa raw của run2 + junction cache nguồn ghim
$env:PYTHONPATH='src'; $env:PYTHONUTF8='1'; $env:PYTHONIOENCODING='utf-8'
foreach ($p in 1,2) {
  python scripts\verify_a_run2.py > det\verify_a_run2.pass$p.txt 2>&1
  python scripts\verify_b.py      > det\verify_b.pass$p.txt      2>&1
  python scripts\verify_cd.py     > det\verify_cd.pass$p.txt     2>&1
  python scripts\verify_e.py      > det\verify_e.pass$p.txt      2>&1
  python scripts\verify_fg.py     > det\verify_fg.pass$p.txt     2>&1
}
```

`verify_a_run2.py` là **bản sao** của `verify_a.py` mà verifier phải sửa tối thiểu (hàm `payload()`
coi text rỗng/không-JSON là `{}`) vì run2 case `A4_100K` trả lỗi schema thay vì payload — đã khai báo
trong `comparison.md`. 4 script còn lại chạy bản gốc của repo, byte-identical.

## Kết quả (2 lần chạy, so từng file)

| script | exit pass1 | exit pass2 | SHA-256 (16 ký tự đầu) pass1 | pass2 | giống nhau |
|---|---|---|---|---|---|
| `verify_a_run2.py` | 0 | 0 | `FFA190EC2230FF83` | `FFA190EC2230FF83` | **IDENTICAL** |
| `verify_b.py` | 0 | 0 | `20C7FB5AF47B5D73` | `20C7FB5AF47B5D73` | **IDENTICAL** |
| `verify_cd.py` | 0 | 0 | `77399B0D22C0C690` | `77399B0D22C0C690` | **IDENTICAL** |
| `verify_e.py` | 0 | 0 | `289643AE92E8D5DB` | `289643AE92E8D5DB` | **IDENTICAL** |
| `verify_fg.py` | 0 | 0 | `83ACB46D90AA6BC5` | `83ACB46D90AA6BC5` | **IDENTICAL** |

Số dòng mỗi lần: A 145 · B 162 · CD 159 · E 510 · FG 356 — bằng nhau giữa hai lần.

## Kết luận

- 5/5 script cho output **byte-identical** giữa hai lần chạy ⇒ verdict của run2 không phụ thuộc thứ
  tự chạy, thời điểm hay trạng thái tiến trình; chúng chỉ là hàm của raw run2 + nguồn ghim
  (`research/cache/git`) trong worktree.
- Điều kiện để tái lập: raw run2 (`docs/blackbox/run2/`, commit `f1002a6`) + junction
  `research/cache` (nguồn ghim) + `data/corpus`. Không có bước nào gọi server hay mạng.
- Giới hạn: đây là kiểm tra **tất định của khâu chấm điểm**, không phải của bản thân lần chạy server
  (run2 chỉ được chạy một lần theo luật; xem `comparison.md` §"một lần chạy").
