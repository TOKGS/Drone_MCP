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

## 4. Bước (2) — sửa nguyên nhân gốc

`src/ardupilot_research_mcp/decoders/crsf.py`:

```python
def c_div(a: int, b: int) -> int:
    """Integer division truncating toward zero, as C does: c_div(-2460, 8) == -307, //  gives -308."""
    quotient = abs(a) // abs(b)
    return -quotient if (a < 0) != (b < 0) else quotient


def ticks_to_us(ticks: int) -> int:
    # crsf_spec/crsf.md: #define TICKS_TO_US(x)  ((x - 992) * 5 / 8 + 1500)
    return c_div((ticks - 992) * 5, 8) + 1500
```

`src/ardupilot_research_mcp/tools/decode_crsf_frame.py`:

- thêm `frames_found` (= số frame hoàn chỉnh, cùng giá trị `frame_count` đã có);
- `all_crc_valid = all(...) if complete else None` — `None` khi 0 frame thay vì `all([]) = True`;
- `warning: "no CRSF frames found"` khi 0 frame;
- `truncated_tail_bytes = len(data) - offset` của frame cụt đầu tiên (chỉ thêm khi có);
- `found = bool(complete)` (trước là `bool(frames)`: khung cụt rỗng vẫn trả found=true, mâu thuẫn
  với `warning`);
- tham số `hex: Annotated[str, Field(max_length=4096)]` → JSON schema có `maxLength: 4096`,
  và kiểm tra runtime trả lỗi gọn `hex string too long: N characters (max 4096)`.

Lý do 4096: frame CRSF tối đa 64 byte = 128 ký tự hex; 4096 đủ cho một loạt frame nhưng chặn
đầu vào 100k ký tự bị quét.

Trong lúc làm, dùng hằng số module trong `Field(max_length=MAX_HEX_CHARS)` thì fail (raw output):

```text
E               pydantic.errors.PydanticUserError: `decode_crsf_frameArguments` is not fully defined; you should define `MAX_HEX_CHARS`, then call `decode_crsf_frameArguments.model_rebuild()`.
```

Nguyên nhân: `from __future__ import annotations` biến chú thích thành chuỗi, mà wrapper
`guarded_pure` (ở `tools/_base.py`, nhánh C sở hữu, KHÔNG sửa) đặt `__signature__` của nó nên
pydantic phân giải tên trong globals của `_base`, nơi không có `MAX_HEX_CHARS`. Cách xử lý trong
phạm vi nhánh D: dùng literal `4096` trong annotation, giữ hằng số `MAX_HEX_CHARS` cho phần
kiểm tra runtime, kèm comment "keep in sync".

## 5. Bước (3) — test mới pass

Lệnh: `python -m pytest tests/test_decoders.py -q`. Output thô:

```text
...........                                                              [100%]
11 passed in 1.78s
```

## 6. Bước (4) — cổng hồi quy

`python -m pytest -q`:

```text
........................................................................ [ 85%]
............                                                             [100%]
84 passed in 25.66s
```

(Baseline 80 passed; 80 + 4 test mới = 84. Không sửa test cũ nào: test cũ trong
`tests/test_decoders.py` không pin `all_crc_valid` cho trường hợp 0 frame, nên không phải đổi.)

`python scripts/fidelity_scan.py`:

```text
crsf_spec         code             7         0
crsf_spec         markdown       150         0
edgetx            code           681         0
expresslrs        block           22         0
expresslrs        code          4834         0
mavlink           block          432         0
----------------------------------------------
TOTAL                          65509         0
fidelity: PASS
```

`python -m research.eval_retrieval --set tests/golden.yaml --aggregate-only`:

```text
set=golden.yaml questions=30 k=5
recall@5 = 30/30 = 1.000
precision@1 = 23/30 = 0.767
MRR = 0.865
```

Không hồi quy: recall@5 = 1.000, P@1 = 0.767 (bằng baseline), fidelity mismatch = 0.

## 7. Ghi chú / giới hạn đã biết

- `frames_found` đếm frame hoàn chỉnh (không tính entry `error` cho frame cụt); được định nghĩa
  bằng `frame_count` hiện có nên hai trường luôn bằng nhau — giữ `frame_count` để không phá
  client cũ.
- Chuỗi 100000 ký tự hex bị chặn bởi `maxLength`/kiểm tra runtime trước khi parse, nên test cho
  ca đó kiểm lỗi "too long"; ca "0 frame sau khi hex hợp lệ" được kiểm riêng bằng `00ff10` và
  `frame[:10]`.
- `truncated_tail_bytes` chỉ xuất hiện khi thật có đuôi cụt; các payload khác giữ nguyên.
- Import `pydantic` (transitive dependency của `mcp==1.30.0`) chỉ dùng cho `Field(max_length=...)`.

- Với client MCP, chuỗi >4096 ký tự bị chặn ngay ở tầng validate schema (`maxLength`); thông báo
  tiếng Anh gọn `hex string too long...` là cho đường gọi hàm trực tiếp (test, script).
