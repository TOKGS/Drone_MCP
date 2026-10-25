# run3, chạy lại 108 case ba lần (sau vòng cải tiến)

Yêu cầu của người dùng: chạy lại bộ 108 case đã đóng băng, chạy nhiều lần, trên OpenCode. Hai việc
tách nhau và cả hai đều đã làm:

- Ba lần chạy bộ 108 case (mục A dưới đây) trên mã đã merge sau vòng cải tiến.
- Một phiên OpenCode với model miễn phí đã gọi tool thật (`docs/blackbox/h/opencode_stream.jsonl`).
  Bộ 108 case không chạy qua OpenCode vì script blackbox tự làm MCP client, không đi qua model;
  chạy qua model sẽ là phép đo của model, không phải của server.

## A. Ba lần chạy, cùng mã, cùng index

Môi trường: worktree cách ly `D:\Skill_tulan\bb-run3` tại commit `ea0a9d4`, index 182,3 MB chép từ
repo chính, `PYTHONPATH=src`, một phiên stdio riêng cho mỗi lần, 110 lần gọi mỗi lần.

```powershell
cd D:\Skill_tulan\bb-run3
$env:PYTHONPATH='src'
foreach ($n in 1,2,3) {
  if (Test-Path docs\blackbox\raw) { Remove-Item docs\blackbox\raw -Recurse -Force }
  python scripts\blackbox_run.py
  Copy-Item docs\blackbox\raw "det\run$n" -Recurse
}
```

| lần | case | thời điểm bắt đầu (`_meta/env.json`) | file |
|---|---|---|---|
| run3-1 | 110 | 21:26 (phiên 1) | 116 |
| run3-2 | 110 | sau đó | 116 |
| run3-3 | 110 | sau đó | 116 |

**Tính tất định: 110/110 payload giống nhau tuyệt đối giữa ba lần.**
Phép so chỉ lấy `response.content[0].text` và `isError`; thời lượng, timestamp, session id bị loại.
Không case nào khác nhau, kể cả ở mức một byte.

## B. run3 so với run2 (bản đã chấm 92/16)

17 case có payload khác. Không case nào đổi chiều pass → fail.

| case | vì sao khác |
|---|---|
| `B2_INDEX_STATUS` | chỉ khác đường dẫn index (`bb-run2` so với `bb-run3`), không phải hành vi |
| `C1` | **sửa thật**: excerpt giờ là định nghĩa `0xD5` của frame CRC, không còn `0xBA` của Command frame |
| `C3`, `C8`, `C12`, `D1`, `D2`, `E_INFO_01..03`, `F_NULL`, `G2_03/10/11/12/13` | `cite_id` đổi vì bước chọn chunk trong document thắng đổi (khớp nguyên từ + heading không hẹp hơn). Cùng document, khác đoạn; verdict không đổi |
| `C4` | cite_id đổi nhưng top-5 vẫn không có `AP_RCProtocol_CRSF.cpp`, vẫn fail |

`G2` (20 `get_chunk`) tự đối chiếu với chính hit C/D của lần chạy đó nên vẫn 20/20, và `G1` lấy mẫu
20 citation từ chính C/D (seed 7) nên vẫn đủ 20.

## C. Điểm của run3

| mục | run2 | run3 |
|---|---|---|
| pass | 92 | **93** |
| fail | 16 | **15** |
| hồi quy (pass → fail) | — | **0** |

Chuyển biến duy nhất: `C1` fail → **pass** (path `crsf_spec/crsf.md` trong top-5 và excerpt chứa
`0xD5`, không chứa `0xBA`).

15 case còn fail, giữ nguyên phân loại của run2:

- **5 lỗi tool**: `B1_LOG_BITMASK`, `B1_SERIAL1_PROTOCOL` (tìm thấy nhưng default là macro chưa quy
  được), `C4`, `C10`, `C11` (file đúng có trong index nhưng không lọt top-5).
- **10 kỳ vọng đóng băng sai**: `A1`, `A2` (chuỗi hex thiếu nibble), `A10_ARMING_CHECK`,
  `B1_ARMING_CHECK`, `B1_WPNAV_SPEED` (tham số không tồn tại ở tag), `C2`, `C3`, `C12` (kỳ vọng coi
  `source_id` như phần của path), `D3`, `D5` (câu trả lời có trong kho / câu thuộc phạm vi an toàn).

Kiểm lại các mục còn lại của run3:

```
E  bypass: refused 11/11 · info answered 4/4
B1 defaults: FS_THR_ENABLE=1 · FS_THR_VALUE=975 · RC_OPTIONS=32 · RC_PROTOCOLS=1
             ARMING_SKIPCHK=0 · LOG_BITMASK raw=DEFAULT_LOG_BITMASK (unresolved)
             SERIAL1_PROTOCOL raw=DEFAULT_SERIAL1_PROTOCOL (unresolved) · BATT_FS_LOW_ACT=0
             ARMING_CHECK found:false + renamed_hint · WPNAV_SPEED found:false
A3 frames_found=1 all_crc_valid=true · A4_XYZ/ODD/EMPTY có error rõ ràng
A4_100K isError (schema max_length), đúng như case cho phép
G1 20 citation lấy mẫu · G2 20/20 khớp hit của chính lần chạy
```

## D. Chấm lại bằng chính 5 script của run1

`_checks/verify_a_run2.run3.txt` và 4 file còn lại là output của 5 script khi chạy với raw của run3
(`verify_a_run2.py` là bản sao có khai báo của `verify_a.py`, cần cho `A4_100K` trả `isError`).
Chúng chỉ đọc raw + nguồn ghim, không gọi server.

## E. Tái lập

```powershell
git -C <repo> log --oneline -1                 # ea0a9d4
# worktree cách ly + index như mục A, rồi:
python scripts\blackbox_run.py                  # 110 lần gọi, một phiên
python scripts\verify_a_run2.py; python scripts\verify_b.py; python scripts\verify_cd.py
python scripts\verify_e.py; python scripts\verify_fg.py
```

Raw của run3 nằm ngay trong thư mục này (111 file case + `_meta/` + `summary.tsv`); thư mục
`_checks/` giữ output của 5 script.
