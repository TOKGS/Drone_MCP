# Nhánh fix/D — lỗi 6: `decode_crsf_frame`

Worktree: `D:\Skill_tulan\wt-D`, nhánh `fix/D`. Baseline (master 7fe0382): `80 passed in 24.22s`.

Phạm vi sửa: `src/ardupilot_research_mcp/tools/decode_crsf_frame.py`,
`src/ardupilot_research_mcp/decoders/crsf.py`, `tests/test_decoders.py`, `docs/fix/D.md`.
KHÔNG sửa `query.py`, `server.py`, `tools/_base.py`, `tools/search_docs.py` (nhánh C sở hữu).

## 1. Nguồn chuẩn: công thức µs

Nguồn ghim (không mạng): `git -C research/cache/git/crsf_spec show HEAD:crsf.md`,
mục "0x16 RC Channels Packed Payload", dòng 526–529. Nguyên văn:

```cpp
#define TICKS_TO_US(x)  ((x - 992) * 5 / 8 + 1500)
#define US_TO_TICKS(x)  ((x - 1500) * 8 / 5 + 992)

// Center (1500µs) = 992
```

Lệnh đã chạy và output thô (rút gọn còn các dòng quanh mục tiêu):

```text
  crsf_pin.md:521:## 0x16 RC Channels Packed Payload
  crsf_pin.md:523:16 channels packed into 22 bytes. ...
  crsf_pin.md:525:```cpp
> crsf_pin.md:526:#define TICKS_TO_US(x)  ((x - 992) * 5 / 8 + 1500)
  crsf_pin.md:527:#define US_TO_TICKS(x)  ((x - 1500) * 8 / 5 + 992)
  crsf_pin.md:528:
  crsf_pin.md:529:// Center (1500µs) = 992
```

`(x - 992) * 5` và `/ 8` là phép chia **số nguyên kiểu C**, cắt về 0:
`-2460 / 8 == -307`; Python `-2460 // 8 == -308`. Vì vậy code hiện tại trả 987 cho tick 172
thay vì 988. Helper `c_div(a, b)` sẽ mô phỏng kiểu C.

## 2. Hiện trạng trước khi sửa (output thô)

Script gọi trực tiếp hàm (không qua MCP), `$env:PYTHONPATH='src'`:

```text
1frame keys ['all_crc_valid', 'byte_count', 'citation', 'crc_polynomial', 'found', 'frame_count', 'frames', 'untrusted']
found/all_crc True True
us [987, 1500, 2011]
badcrc False
empty {'found': False, 'error': 'no hex bytes supplied'}
nonhex {'found': False, 'error': 'no hex bytes supplied'}
100k 8
```

Suy ra: thiếu `frames_found`, thiếu `warning` khi 0 frame, thiếu `truncated_tail_bytes`,
`all_crc_valid` trả `True` khi 0 frame (all() trên list rỗng), µs sai ở phép chia âm,
không có giới hạn độ dài `hex`.

## 3. Bước (1) — test mới, đang fail

Test thêm vào `tests/test_decoders.py`, tự sinh vector bằng encoder tham chiếu viết ngay trong
file test (CRC8 0xD5, sync 0xC8, type 0x16, payload 22 byte = 16 kênh × 11 bit little-endian,
CRC trên Type+Payload) và `random.Random(20240607)` cho kênh trong [172, 1811].
Không import code dự án cho phần tham chiếu; các số 988/1500/2011 kiểm bằng
`ref_ticks_to_us` độc lập.

Lệnh: `python -m pytest tests/test_decoders.py -q`. Output thô:

```text
================================== FAILURES ===================================
__________ test_crsf_tool_reports_frames_crc_and_us_with_c_semantics __________
    payload = decode_crsf_frame(frame.hex())
    assert payload["found"] is True
>   assert payload["frames_found"] == 1
E   KeyError: 'frames_found'
tests\test_decoders.py:126: KeyError
________________ test_crsf_tool_zero_frames_and_truncated_tail ________________
    cut = decode_crsf_frame(frame[:10].hex())
>   assert cut["frames_found"] == 0
E   KeyError: 'frames_found'
tests\test_decoders.py:152: KeyError
___________ test_decode_crsf_frame_hex_is_capped_at_4096_characters ___________
    too_long = decode_crsf_frame("c8" * 2500)      # 5000 hex chars, over the cap
>   assert too_long["found"] is False
E   assert True is False
tests\test_decoders.py:179: AssertionError
=========================== short test summary info ============================
FAILED tests/test_decoders.py::test_crsf_tool_reports_frames_crc_and_us_with_c_semantics
FAILED tests/test_decoders.py::test_crsf_tool_zero_frames_and_truncated_tail
FAILED tests/test_decoders.py::test_decode_crsf_frame_hex_is_capped_at_4096_characters
3 failed, 8 passed in 1.55s
[exit code: 1]
```
