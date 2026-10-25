# F + G1 + G2 — đầu vào đối kháng (F) và kiểm trích dẫn (G1/G2)

Người kiểm: **fg-citations** (verifier độc lập), ngày 2026-10-25. Task `task-5`.

Nguồn duy nhất (chỉ đọc): 12 file `docs/blackbox/raw/F_*.json`, 20 file `docs/blackbox/raw/G2_*.json`,
`docs/blackbox/raw/_meta/g1_sample.json`, `docs/blackbox/raw/C1.json … C12.json`, `D1.json … D5.json`,
`docs/blackbox/raw/summary.tsv`, `raw/_meta/tools_list.json`, `raw/_meta/server-stderr.log`,
`raw/_meta/env.json`, `tests/blackbox_cases.md` mục F/G (file đóng băng, **KHÔNG sửa**), và git object
store `research/cache/git/<repo>` (mỗi repo `git rev-parse HEAD` = pin ghi trong `raw/_meta/env.json:4-12`).

**Không gọi MCP server. Không chạy lại case nào.** Script kiểm: `scripts/verify_fg.py` (Python stdlib,
chỉ đọc file; `python scripts/verify_fg.py f|g1|g2|md|render`).

Quy ước trích dẫn: `docs/blackbox/raw/<CASE>.json:<dòng>`. Trong 11/12 file F và 20/20 file G2,
`response.content[0].text` là **một dòng duy nhất** ở L27; `response.structuredContent.result` là bản
pretty-print của **đúng** object đó — script đã kiểm `json.loads(content[0].text) == structuredContent.result`
cho **11/11** case F có `structuredContent` (`F_MB` có `"structuredContent": null` tại
`raw/F_MB.json:30`) và **20/20** case G2. Vì vậy phần JSON dưới đây khi trích theo dòng `:27` là đúng
payload thô, còn khối `structuredContent` chỉ là cùng nội dung dễ đọc.

---

## 0. Kết luận một khối

| Nhóm | Kết quả | Bằng chứng |
|---|---|---|
| F — crash | **0/12 crash**. Sau mỗi case F còn 22–33 case trong `summary.tsv` vẫn trả lời tới dòng 111 (`G2_20`) | `raw/summary.tsv:78-89` (12 dòng F) và `:90-111`; `raw/_meta/server-stderr.log:4-222` có 110 `CallToolRequest`, 0 dòng `Traceback/ERROR` |
| F — treo > 10 s | **0/12**. `duration_ms` lớn nhất = 105.1 | `raw/F_FIND_QUOTE.json:20` `"duration_ms": 105.1`; 11 case còn lại 6.1–100.0 (`summary.tsv:78-88`) |
| F — lộ đường dẫn tuyệt đối | **0/12**. 0 match trên mọi string đã decode của payload + `structuredContent` | bảng F cột "lộ đường dẫn tuyệt đối?" — đều `không (0 match)` |
| F — lỗi xử lý đầu vào | **1** (`F_MB`): `isError: true` + message thô của SQLite | `raw/F_MB.json:23`, `raw/F_MB.json:27` (chi tiết **F-01**) |
| G1 — URL chứa pin, không `main/master/HEAD` | **20/20** (7 URL dùng SHA đầy đủ, 13 URL dùng tag; cả 13 tag đều resolve đúng pin) | bảng G1 cột "pin trong url?"; `raw/_meta/g1_sample.json:16,41,66,91,116,141,166,191,216,241,266,291,316,341,366,391,416,441,466,491` |
| G1 — excerpt khớp khoảng dòng tại pin | **20/20** theo 3 mức: **6** khớp nguyên văn toàn range, **12** khớp tiền tố 600 ký tự cắt giữa dòng, **2** khớp tiền tố 600 sau khi bỏ 1 dòng trống đầu (chi tiết **G-01**) | bảng G1 cột "dòng khớp?" |
| G1 — excerpt ≤ 600 ký tự | **20/20**; dài nhất = 600 | bảng G1 cột "excerpt ≤600?" |
| G2 — `get_chunk` trả cùng nội dung với hit C/D | **20/20 khớp, 0 mismatch**; `field_diff` = 0/20; `text` khớp nguồn tại pin 16/20 từng byte, 4/20 lệch đúng 1 ký tự trắng biên | bảng G2; `raw/G2_01..G2_20.json:27` |

Phân loại theo Luật 3: **F-01 = TOOL SAI** (1 lỗi), **G-01 = KHÔNG XÁC ĐỊNH** (1 điểm chưa đủ căn cứ),
**0** case "KỲ VỌNG CỦA TÔI SAI".

Kỳ vọng đóng băng dùng để phán: `tests/blackbox_cases.md:68` — "Pass = không crash, không treo quá 10 giây,
không lộ đường dẫn tuyệt đối trên máy" (F); `tests/blackbox_cases.md:71-72` (G1/G2).

---

## 1. Bảng F (12 case)

| # | case | input | duration_ms | isError | crash? | lộ đường dẫn tuyệt đối? | verdict | dẫn chứng raw |
|---|---|---|---|---|---|---|---|---|
| 1 | F_QUOTE | `"` | 15.0 | False | không; 33/33 case sau trong summary.tsv (tới G2_20, dòng 111) vẫn trả lời | không (0 match) | PASS: không crash, không treo, không lộ | `raw/F_QUOTE.json`:20 (duration), :23 (isError), :27 (text); `raw/summary.tsv`:78 |
| 2 | F_STAR | `*` | 12.9 | False | không; 32/32 case sau trong summary.tsv (tới G2_20, dòng 111) vẫn trả lời | không (0 match) | PASS: không crash, không treo, không lộ | `raw/F_STAR.json`:20 (duration), :23 (isError), :27 (text); `raw/summary.tsv`:79 |
| 3 | F_NEAR | `NEAR(` | 56.5 | False | không; 31/31 case sau trong summary.tsv (tới G2_20, dòng 111) vẫn trả lời | không (0 match) | PASS: không crash, không treo, không lộ | `raw/F_NEAR.json`:20 (duration), :23 (isError), :27 (text); `raw/summary.tsv`:80 |
| 4 | F_ORAND | `OR AND` | 16.3 | False | không; 30/30 case sau trong summary.tsv (tới G2_20, dòng 111) vẫn trả lời | không (0 match) | PASS: không crash, không treo, không lộ | `raw/F_ORAND.json`:20 (duration), :23 (isError), :27 (text); `raw/summary.tsv`:81 |
| 5 | F_SQLI | `'; DROP TABLE chunks;--` | 36.7 | False | không; 29/29 case sau trong summary.tsv (tới G2_20, dòng 111) vẫn trả lời | không (0 match) | PASS: không crash, không treo, không lộ | `raw/F_SQLI.json`:20 (duration), :23 (isError), :27 (text); `raw/summary.tsv`:82 |
| 6 | F_MB | `'A' × 1000000` (1 MB) | 37.1 | True | không; 28/28 case sau trong summary.tsv (tới G2_20, dòng 111) vẫn trả lời | không (0 match) | PASS tiêu chí F; NHƯNG lỗi xử lý đầu vào (xem F-01) | `raw/F_MB.json`:20 (duration), :23 (isError), :27 (text); `raw/summary.tsv`:83 |
| 7 | F_UNICODE | `🚁 tín hiệu CRSF bị mất 😀` | 39.8 | False | không; 27/27 case sau trong summary.tsv (tới G2_20, dòng 111) vẫn trả lời | không (0 match) | PASS: không crash, không treo, không lộ | `raw/F_UNICODE.json`:20 (duration), :23 (isError), :27 (text); `raw/summary.tsv`:84 |
| 8 | F_NULL | `CRSF\u0000crc` | 41.0 | False | không; 26/26 case sau trong summary.tsv (tới G2_20, dòng 111) vẫn trả lời | không (0 match) | PASS: không crash, không treo, không lộ | `raw/F_NULL.json`:20 (duration), :23 (isError), :27 (text); `raw/summary.tsv`:85 |
| 9 | F_CHUNK_BAD | cite_id `does-not-exist-0000` | 6.3 | False | không; 25/25 case sau trong summary.tsv (tới G2_20, dòng 111) vẫn trả lời | không (0 match) | PASS: không crash, không treo, không lộ | `raw/F_CHUNK_BAD.json`:20 (duration), :23 (isError), :27 (text); `raw/summary.tsv`:86 |
| 10 | F_CHUNK_PATH | cite_id `../../x` | 6.1 | False | không; 24/24 case sau trong summary.tsv (tới G2_20, dòng 111) vẫn trả lời | không (0 match) | PASS: không crash, không treo, không lộ | `raw/F_CHUNK_PATH.json`:20 (duration), :23 (isError), :27 (text); `raw/summary.tsv`:87 |
| 11 | F_FIND_STAR | symbol_or_file `*` | 100.0 | False | không; 23/23 case sau trong summary.tsv (tới G2_20, dòng 111) vẫn trả lời | không (0 match) | PASS: không crash, không treo, không lộ | `raw/F_FIND_STAR.json`:20 (duration), :23 (isError), :27 (text); `raw/summary.tsv`:88 |
| 12 | F_FIND_QUOTE | symbol_or_file `" OR "` | 105.1 | False | không; 22/22 case sau trong summary.tsv (tới G2_20, dòng 111) vẫn trả lời | không (0 match) | PASS: không crash, không treo, không lộ | `raw/F_FIND_QUOTE.json`:20 (duration), :23 (isError), :27 (text); `raw/summary.tsv`:89 |

Cách đo 4 cột phán xét:

1. **crash?** — Case được coi là không crash khi (a) `transport_error` = `null`
   (12/12 file F, dòng 21), (b) các case **sau** nó trong `summary.tsv` vẫn có `duration_ms` và
   `transport_error=False`, và (c) log stderr của server không có `Traceback`/`ERROR`.
   Bằng chứng toàn cục: `raw/summary.tsv:90-111` (22 dòng sau khối F: `A1_RERUN_CORRECTED`,
   `A2_RERUN_CORRECTED`, `G2_01..G2_20`) đều có `duration_ms` 8.2–11.6 ms và `transport_error=False`;
   `raw/_meta/server-stderr.log` dài 222 dòng, đếm được **110** dòng `CallToolRequest` + 1 `ListToolsRequest`,
   0 dòng khớp `Traceback|ERROR|CRITICAL|Exception|shutting down`.
2. **treo?** — `duration_ms` < 10000; giá trị đọc từ `"duration_ms"` (dòng 20 của mỗi file F).
3. **lộ đường dẫn tuyệt đối?** — script decode payload rồi quét **mọi** string (kể cả
   `structuredContent`) với các mẫu: `[Dd]:\`, `[Cc]:\`, `skill_tulan`, `[Uu]sers\`, `/home/`, `/etc/`,
   cộng thêm `file:///`, `AppData`, `/usr/`, `/var/`, `/mnt/`, `research\cache`, `\\?\`.
   **12/12 case: 0 match.** (Quét chéo trên text JSON thô thấy 4 chuỗi dạng `s:\\`, `t:\\`, `y:\\`, `r:\\`
   trong `raw/F_SQLI.json:27` — đó là escape JSON của `\t` trong excerpt code Python
   (`sys.stdout.write('\t%-10s\t:\t[' % s)`), không phải ổ đĩa; trên string đã decode là 0 match.)
4. **verdict** — theo đúng 3 vế của `tests/blackbox_cases.md:68`, cộng ghi chú lỗi phát hiện thêm.

---

## 2. Bằng chứng thô từng case F + phán xét

### F_QUOTE — `search_docs(query='"')`

- `raw/F_QUOTE.json:20` `"duration_ms": 15.0`; `:21` `"transport_error": null`; `:23` `"isError": false`.
- payload `raw/F_QUOTE.json:27`:
  ```json
  {"found": false, "query": "\"", "results": [], "candidates": [], "note": "query has no searchable tokens", "result_count": 0}
  ```
- Phán xét: dấu `"` không làm vỡ FTS; tool trả `found:false` + lý do rõ. Không crash, 15.0 ms, 0 path leak.
  **PASS tiêu chí F.**

### F_STAR — `search_docs(query='*')`

- `raw/F_STAR.json:20` `"duration_ms": 12.9`; `:23` `"isError": false`.
- payload `raw/F_STAR.json:27`:
  ```json
  {"found": false, "query": "*", "results": [], "candidates": [], "note": "query has no searchable tokens", "result_count": 0}
  ```
- Phán xét: `*` (toán tử FTS) được xử lý như "không có token tìm được", không nổ. 12.9 ms, 0 path leak.
  **PASS tiêu chí F.**

### F_NEAR — `search_docs(query='NEAR(')`

- `raw/F_NEAR.json:20` `"duration_ms": 56.5`; `:23` `"isError": false`.
- payload `raw/F_NEAR.json:27` (đầu): `{"found": true, "query": "NEAR(", … "results": [ {"cite_id": "ardupilot#d110ccd20f0951c7", …}`;
  cuối: `"note": null, "result_count": 5`.
- Phán xét: `NEAR(` không mở được cú pháp FTS (không có nhánh lỗi SQL), trả 5 kết quả hạng bình thường
  (hit đầu `libraries/AP_Math/tests/test_math.cpp#L548-L568`, excerpt chứa `EXPECT_NEAR(`).
  56.5 ms, 0 path leak. **PASS tiêu chí F.**

### F_ORAND — `search_docs(query='OR AND')`

- `raw/F_ORAND.json:20` `"duration_ms": 16.3`; `:23` `"isError": false`.
- payload `raw/F_ORAND.json:27`:
  ```json
  {"found": false, "query": "OR AND", "results": [], "candidates": [], "note": "query has no searchable tokens", "result_count": 0}
  ```
- Phán xét: hai toán tử FTS trần bị loại vì không có token nội dung. 16.3 ms, 0 path leak.
  **PASS tiêu chí F.**

### F_SQLI — `search_docs(query="'; DROP TABLE chunks;--")`

- `raw/F_SQLI.json:20` `"duration_ms": 36.7`; `:23` `"isError": false`.
- payload `raw/F_SQLI.json:27` (đầu): `{"found": true, "query": "'; DROP TABLE chunks;--", … "results": [ {"cite_id": "crsf_spec#dcf5667793214464", …}`;
  cuối: `"note": null, "result_count": 7`.
- Phán xét: chuỗi injection được coi là **văn bản** (không phải SQL): trả 7 kết quả, `isError=false`,
  không có lỗi SQL nào. Bằng chứng index còn nguyên sau đó: 20/20 case `G2_*` chạy **sau** F_SQLI vẫn trả
  nội dung thật từ index (`raw/summary.tsv:92-111`; ví dụ `raw/G2_01.json:27` có `"text"` 490 ký tự khớp nguồn).
  36.7 ms, 0 path leak. **PASS tiêu chí F.**

### F_MB — `search_docs(query='A' × 1 000 000)`

- `raw/F_MB.json:20` `"duration_ms": 37.1`; `:21` `"transport_error": null`; `:23` `"isError": true`;
  `:30` `"structuredContent": null`.
- payload `raw/F_MB.json:27` — nguyên văn:
  ```
  Error executing tool search_docs: LIKE or GLOB pattern too complex
  ```
- Phán xét: **không crash** (28 case sau vẫn trả lời, `raw/summary.tsv:84-111`; stderr 110 `CallToolRequest`,
  0 `Traceback`), **không treo** (37.1 ms), **không lộ path** (0 match). Nhưng đây là **lỗi xử lý đầu vào** —
  xem **F-01**: message là lỗi engine SQLite thô, không phải thông báo kiểm tra độ dài.
  Theo đúng 3 vế của `tests/blackbox_cases.md:68`: **PASS**; theo chất lượng đầu vào: **TOOL SAI**.

### F_UNICODE — `search_docs(query='🚁 tín hiệu CRSF bị mất 😀')`

- `raw/F_UNICODE.json:20` `"duration_ms": 39.8`; `:23` `"isError": false`.
- payload `raw/F_UNICODE.json:27` (đầu): `{"found": true, "query": "🚁 tín hiệu CRSF bị mất 😀", … "results": [ {"cite_id": "expresslrs#36cc06e0835691be", …}`;
  cuối: `"note": null, "result_count": 6`.
- Phán xét: emoji + tiếng Việt được echo **nguyên văn** trong `query` (không mojibake); `query_expanded: null`
  và `expansions: []` nên **không** có mở rộng glossary trong case này — tool khớp trực tiếp trên token và
  trả 6 hit (hit đầu `src/include/crsf_protocol.h#L89-L126`). 39.8 ms, 0 path leak.
  **PASS tiêu chí F.**

### F_NULL — `search_docs(query='CRSF\x00crc')`

- `raw/F_NULL.json:20` `"duration_ms": 41.0`; `:23` `"isError": false`.
- payload `raw/F_NULL.json:27` (đầu): `{"found": true, "query": "CRSF\u0000crc", …`; cuối: `"note": null, "result_count": 5`.
- Phán xét: byte NUL (0x00) trong query không làm gãy JSON-RPC/SQLite: query được echo lại đúng dạng
  `\u0000`, trả 5 kết quả (`expresslrs#952a9101ba9c0989`, `crsf_protocol.h#L38-L53`).
  41.0 ms, 0 path leak. **PASS tiêu chí F.**

### F_CHUNK_BAD — `get_chunk(cite_id='does-not-exist-0000')`

- `raw/F_CHUNK_BAD.json:20` `"duration_ms": 6.3`; `:23` `"isError": false`.
- payload `raw/F_CHUNK_BAD.json:27`:
  ```json
  {"found": false, "error": "bad cite_id 'does-not-exist-0000'; expected '<source>#<hash>'"}
  ```
- Phán xét: từ chối sạch bằng `found:false` + mô tả định dạng mong đợi. 6.3 ms, 0 path leak.
  **PASS tiêu chí F.**

### F_CHUNK_PATH — `get_chunk(cite_id='../../x')`

- `raw/F_CHUNK_PATH.json:20` `"duration_ms": 6.1`; `:23` `"isError": false`.
- payload `raw/F_CHUNK_PATH.json:27`:
  ```json
  {"found": false, "error": "bad cite_id '../../x'; expected '<source>#<hash>'"}
  ```
- Phán xét: cite_id chứa `../` bị từ chối theo định dạng, **không** bị dùng làm đường dẫn; chuỗi `'../../x'`
  trong message là **input của client** được echo, không phải đường dẫn trên máy chủ. 6.1 ms, 0 path leak.
  **PASS tiêu chí F.**

### F_FIND_STAR — `find_source(symbol_or_file='*')`

- `raw/F_FIND_STAR.json:20` `"duration_ms": 100.0`; `:23` `"isError": false`.
- payload `raw/F_FIND_STAR.json:27` (đầu): `{"found": true, "query": "*", "mode": "symbol", "repo_filter": null, "hits": [ {"path": "crsf.md", "lines": [ 121, 127 ], …`;
  có 12 hit, mọi hit đều kèm `url` pin `a73f7dc538…` và path tương đối.
- Phán xét: `*` không bị coi là wildcard/LIKE, không lỗi; 100.0 ms (< 10 s), 0 path leak.
  **PASS tiêu chí F.**

### F_FIND_QUOTE — `find_source(symbol_or_file='" OR "')`

- `raw/F_FIND_QUOTE.json:20` `"duration_ms": 105.1`; `:23` `"isError": false`.
- payload `raw/F_FIND_QUOTE.json:27` (đầu): `{"found": true, "query": "\" OR \"", "mode": "symbol", "repo_filter": null, "hits": [ {"path": "crsf.md", "lines": [ 887, 891 ], …`;
  có 6 hit.
- Phán xét: chuỗi `" OR "` không chèn được mệnh đề SQL; 105.1 ms (< 10 s), 0 path leak.
  **PASS tiêu chí F.** (Đây là `duration_ms` lớn nhất của cả nhóm F, vẫn dưới ngưỡng 10 000 ms ~95 lần.)

---

## 3. G1 — 20 trích dẫn lấy mẫu (seed 7, pool 72)

### 3.1 Cách kiểm

Mẫu: `raw/_meta/g1_sample.json` — `pool_size` = 72, `sampled` = 20, `seed` = 7
(`raw/_meta/g1_sample.json:2-5`). Script đếm lại từ chính payload C/D: **72** `cite_id` duy nhất trong
`results` của `C1..C12` + `D1..D5` (53 + 19), **không trùng**; 20/20 `cite_id` của mẫu có mặt trong đó;
20/20 object trong mẫu **bằng đúng** object gốc trong file C/D (`==` trên toàn bộ 20 khóa) — mẫu không bị
sửa tay.

Ba phép kiểm cho mỗi mục:

**(a) Pin trong URL.** URL phải có dạng
`https://github.com/<owner>/<repo>/blob/<ref>/<path>#L<a>-L<b>`, trong đó:
`<owner>/<repo>` = `repo` của citation, `<path>` = `path`, `(a,b)` = `lines`, và `<ref>` = `ref`.
Không được chứa segment `main`, `master`, `HEAD`. Với `<ref>` là tag, script chạy
`git -C research/cache/git/<source> rev-parse '<ref>^{commit}'` và đòi kết quả **bằng đúng pin**
trong `raw/_meta/env.json:4-12`; với `<ref>` là SHA thì đòi **bằng đúng pin**. Ngoài ra đòi
`pinned: true`.

**(b) Nội dung tại khoảng dòng.** Dựng lại range bằng:

```
git -C research/cache/git/<source> show <pin>:<path>      # <pin> = dòng 4-12 của raw/_meta/env.json
```

rồi lấy `lines = text.splitlines()` (không có newline cuối) và
`block = "\n".join(lines[a-1:b])` với `[a,b] = citation.lines`. So `excerpt` với `block` theo thứ tự:

1. **exact** — `excerpt == block` (khớp nguyên văn toàn range);
2. **raw prefix** — `block.startswith(excerpt)`; nếu đúng và `len(block) > len(excerpt)` thì excerpt là
   600 ký tự đầu của range (bị cắt giữa dòng), và script ghi lại 20 ký tự quanh điểm cắt;
3. **raw prefix sau khi bỏ dòng trống đầu** — `block.lstrip("\r\n").startswith(excerpt)` (dùng cho
   trường hợp `line_start` trỏ vào dòng trống — xem **G-01**);
4. nếu không mức nào đúng thì đánh "KHÔNG khớp" kèm vị trí lệch đầu tiên.

Lý do dùng tiền tố: chính `tools/list` khai báo excerpt là "a **verbatim excerpt of at most 600
characters**" (`raw/_meta/tools_list.json:5`), nên excerpt dài ≥ 600 của một range dài hơn 600 ký tự
**phải** là tiền tố của range. Điều này cũng là lý do cột "excerpt ≤600" là một phép kiểm riêng.

**(c) Độ dài excerpt** — `len(excerpt)` (đếm ký tự Unicode) ≤ 600; script cũng ghi `len(bytes UTF-8)`.

### 3.2 Bảng G1

| # | cite_id | pin trong url? | dòng khớp? | excerpt ≤600? | git show đã dùng | dẫn chứng raw |
|---|---|---|---|---|---|---|
| 1 | `ardupilot_wiki#f8ab2e4e432c8a39` | có: `828de1f225dace34b482e63abaab15d25b2b1732` → `828de1f225…` | khớp nguyên văn toàn range (490/490 ký tự) | có (490) | `git -C research/cache/git/ardupilot_wiki show 828de1f225dace34b482e63abaab15d25b2b1732:common/source/docs/common-rc-systems.rst` | `raw/_meta/g1_sample.json`:8; `raw/C10.json`:42 |
| 2 | `expresslrs#fe280216f9d9cd5e` | có: `4.1.0` → `a9d4a9cb5b…` | khớp tiền tố 600/1625 ký tự (cắt tại 600, giữa dòng: 2_t mspPayloadLen = getPayloadLen(data, ) | có (600) | `git -C research/cache/git/expresslrs show a9d4a9cb5b5687c4c9d7e9e7fbdf44ad93651da6:src/lib/CRSF2MSP/msp2crsf.cpp` | `raw/_meta/g1_sample.json`:33; `raw/C4.json`:142 |
| 3 | `expresslrs_docs#9b82e6e086b6b0f5` | có: `5ed656b6ebc7a38b6012297cf40fe5bc87232bed` → `5ed656b6eb…` | khớp nguyên văn toàn range (514/514 ký tự) | có (514) | `git -C research/cache/git/expresslrs_docs show 5ed656b6ebc7a38b6012297cf40fe5bc87232bed:docs/info/init-rate.md` | `raw/_meta/g1_sample.json`:58; `raw/C12.json`:42 |
| 4 | `edgetx#a2f1bf22a7c437f0` | có: `v2.12.5` → `0ebe2e98b2…` | khớp tiền tố 600/1320 ký tự (cắt tại 600, giữa dòng: \n    g_tryBaudIdx = (uint8_t)((g_tryBaud) | có (600) | `git -C research/cache/git/edgetx show 0ebe2e98b2085e2251ad6773b26c8a7ab8dd3e99:radio/src/targets/hrs/v15/crsf_measure.cpp` | `raw/_meta/g1_sample.json`:83; `raw/C2.json`:67 |
| 5 | `ardupilot#0adec6354cbdf85d` | có: `Copter-4.7.2` → `fb77356789…` | khớp tiền tố 600/2993 ký tự (cắt tại 600, giữa dòng: ABLED\n    void start_bind(void) override) | có (600) | `git -C research/cache/git/ardupilot show fb773567896014da007bca58358704d4a0d8516f:libraries/AP_RCProtocol/AP_RCProtocol_CRSF.h` | `raw/_meta/g1_sample.json`:108; `raw/C2.json`:142 |
| 6 | `ardupilot#84faa083fcae8409` | có: `Copter-4.7.2` → `fb77356789…` | khớp tiền tố 600/2476 ký tự sau khi bỏ 1 dòng trống đầu (cắt tại 600) | có (600) | `git -C research/cache/git/ardupilot show fb773567896014da007bca58358704d4a0d8516f:libraries/AP_RCProtocol/AP_RCProtocol_CRSF.cpp` | `raw/_meta/g1_sample.json`:133; `raw/C3.json`:94 |
| 7 | `ardupilot_wiki#c2593dacde94604e` | có: `828de1f225dace34b482e63abaab15d25b2b1732` → `828de1f225…` | khớp nguyên văn toàn range (551/551 ký tự) | có (551) | `git -C research/cache/git/ardupilot_wiki show 828de1f225dace34b482e63abaab15d25b2b1732:common/source/docs/common-crsf-telemetry.rst` | `raw/_meta/g1_sample.json`:158; `raw/C11.json`:67 |
| 8 | `expresslrs#fbe624b4e6902251` | có: `4.1.0` → `a9d4a9cb5b…` | khớp tiền tố 600/1746 ký tự (cắt tại 600, giữa dòng: axPacketSize()\n{\n    const int LUA_CHUNK) | có (600) | `git -C research/cache/git/expresslrs show a9d4a9cb5b5687c4c9d7e9e7fbdf44ad93651da6:src/lib/Handset/CRSFHandset.cpp` | `raw/_meta/g1_sample.json`:183; `raw/C2.json`:92 |
| 9 | `ardupilot#52da62b485d7dbdd` | có: `Copter-4.7.2` → `fb77356789…` | khớp tiền tố 600/904 ký tự (cắt tại 600, giữa dòng: tate) {\n    case SubMode::WAIT_FOR_PATH_) | có (600) | `git -C research/cache/git/ardupilot show fb773567896014da007bca58358704d4a0d8516f:ArduCopter/mode_smart_rtl.cpp` | `raw/_meta/g1_sample.json`:208; `raw/C7.json`:67 |
| 10 | `crsf_spec#90c2ac349451f6c9` | có: `a73f7dc5386e5b8744aa4a23b3af5354ee0d4c92` → `a73f7dc538…` | khớp nguyên văn toàn range (491/491 ký tự) | có (491) | `git -C research/cache/git/crsf_spec show a73f7dc5386e5b8744aa4a23b3af5354ee0d4c92:crsf.md` | `raw/_meta/g1_sample.json`:233; `raw/C1.json`:92 |
| 11 | `ardupilot#d2d15d1ffa0b19e9` | có: `Copter-4.7.2` → `fb77356789…` | khớp tiền tố 600/743 ký tự sau khi bỏ 1 dòng trống đầu (cắt tại 600) | có (600) | `git -C research/cache/git/ardupilot show fb773567896014da007bca58358704d4a0d8516f:libraries/AP_RCProtocol/AP_RCProtocol_CRSF.cpp` | `raw/_meta/g1_sample.json`:258; `raw/C2.json`:42 |
| 12 | `ardupilot#0566f786fd5d051a` | có: `Copter-4.7.2` → `fb77356789…` | khớp tiền tố 600/2982 ký tự (cắt tại 600, giữa dòng: or=(const Bitmask&other) {\n        memcp) | có (600) | `git -C research/cache/git/ardupilot show fb773567896014da007bca58358704d4a0d8516f:libraries/AP_Common/Bitmask.h` | `raw/_meta/g1_sample.json`:283; `raw/D4.json`:44 |
| 13 | `ardupilot#9db38568cd9df5e4` | có: `Copter-4.7.2` → `fb77356789…` | khớp tiền tố 600/1144 ký tự (cắt tại 600, giữa dòng:  controller\n    wp_nav->wp_and_spline_in) | có (600) | `git -C research/cache/git/ardupilot show fb773567896014da007bca58358704d4a0d8516f:ArduCopter/mode_rtl.cpp` | `raw/_meta/g1_sample.json`:308; `raw/C7.json`:42 |
| 14 | `ardupilot#bca71e018b58cdcb` | có: `Copter-4.7.2` → `fb77356789…` | khớp nguyên văn toàn range (265/265 ký tự) | có (265) | `git -C research/cache/git/ardupilot show fb773567896014da007bca58358704d4a0d8516f:libraries/AP_Math/tests/test_crc8.cpp` | `raw/_meta/g1_sample.json`:333; `raw/C1.json`:142 |
| 15 | `edgetx#d3d997571493b805` | có: `v2.12.5` → `0ebe2e98b2…` | khớp tiền tố 600/2975 ký tự (cắt tại 600, giữa dòng: F_MEASURE_POL_NORMAL;\n  }\n}\n\nvoid consum) | có (600) | `git -C research/cache/git/edgetx show 0ebe2e98b2085e2251ad6773b26c8a7ab8dd3e99:radio/src/targets/hrs/v15/crsf_measure.cpp` | `raw/_meta/g1_sample.json`:358; `raw/C4.json`:42 |
| 16 | `ardupilot_wiki#f504ee227905786f` | có: `828de1f225dace34b482e63abaab15d25b2b1732` → `828de1f225…` | khớp tiền tố 600/627 ký tự (cắt tại 600, giữa dòng: antly higher values are needed for a Qua) | có (600) | `git -C research/cache/git/ardupilot_wiki show 828de1f225dace34b482e63abaab15d25b2b1732:plane/source/docs/quadplane-parameters.rst` | `raw/_meta/g1_sample.json`:383; `raw/D3.json`:67 |
| 17 | `ardupilot#ade96649dd76f1f9` | có: `Copter-4.7.2` → `fb77356789…` | khớp tiền tố 600/2220 ký tự (cắt tại 600, giữa dòng: ride;\n    bool arm(AP_Arming::Method met) | có (600) | `git -C research/cache/git/ardupilot show fb773567896014da007bca58358704d4a0d8516f:ArduCopter/AP_Arming_Copter.h` | `raw/_meta/g1_sample.json`:408; `raw/C8.json`:142 |
| 18 | `ardupilot_wiki#a13e972632dda146` | có: `828de1f225dace34b482e63abaab15d25b2b1732` → `828de1f225…` | khớp nguyên văn toàn range (512/512 ký tự) | có (512) | `git -C research/cache/git/ardupilot_wiki show 828de1f225dace34b482e63abaab15d25b2b1732:plane/source/docs/quadplane-overview.rst` | `raw/_meta/g1_sample.json`:433; `raw/D3.json`:42 |
| 19 | `ardupilot#9345259ec64dd06e` | có: `Copter-4.7.2` → `fb77356789…` | khớp tiền tố 600/1546 ký tự (cắt tại 600, giữa dòng: fined(CRSF_DEBUG) \\|\\| defined(CRSF_DEBUG_) | có (600) | `git -C research/cache/git/ardupilot show fb773567896014da007bca58358704d4a0d8516f:libraries/AP_RCProtocol/AP_RCProtocol_CRSF.cpp` | `raw/_meta/g1_sample.json`:458; `raw/C1.json`:117 |
| 20 | `expresslrs_docs#34d87707cbd6f1b9` | có: `5ed656b6ebc7a38b6012297cf40fe5bc87232bed` → `5ed656b6eb…` | khớp tiền tố 600/826 ký tự (cắt tại 600, giữa dòng: acket rates of 50Hz, 150Hz, 250Hz, 500Hz) | có (600) | `git -C research/cache/git/expresslrs_docs show 5ed656b6ebc7a38b6012297cf40fe5bc87232bed:docs/software/switch-config.md` | `raw/_meta/g1_sample.json`:483; `raw/C12.json`:92 |

### 3.3 Tổng hợp G1

- Pin: **20/20** URL mang pin. **7** URL dùng SHA đầy đủ (`ardupilot_wiki` ×4, `crsf_spec` ×1,
  `expresslrs_docs` ×2), **13** URL dùng tag: `Copter-4.7.2` ×9, `4.1.0` ×2, `v2.12.5` ×2 —
  cả 13 tag resolve trong object store đúng pin SHA (`fb77356…`, `a9d4a9c…`, `0ebe2e9…`).
  Không URL nào chứa `main`/`master`/`HEAD`; 20/20 có `pinned: true`.
- Nội dung: **6/20** khớp nguyên văn **toàn bộ** range (490/490, 514/514, 551/551, 491/491, 265/265,
  512/512 ký tự); **12/20** khớp **tiền tố 600 ký tự** của range (range dài 627–2993 ký tự, điểm cắt nằm
  giữa dòng); **2/20** (mục 6 và 11) khớp tiền tố 600 ký tự **sau khi bỏ 1 dòng trống đầu** vì
  `line_start` (476 và 689) là dòng trống — xem **G-01**. Không mục nào lệch nội dung.
- Độ dài: **20/20** `len(excerpt) ≤ 600`, dài nhất = 600 (14 mục), ngắn nhất = 265 (mục 14).

---

## 4. G2 — 20 lời gọi `get_chunk(cite_id)` cho đúng 20 `cite_id` của G1

### 4.1 Cách kiểm

Mỗi `raw/G2_XX.json` gọi `get_chunk` với `cite_id` ở `arguments.cite_id` (dòng 6) và `note` (dòng 3) ghi
rõ cite_id. Script so **payload của G2** với **object citation gốc** trong file C/D (bản ghi gốc, không
phải bản mẫu `g1_sample.json`), theo 3 lớp:

1. **metadata** — 12 khóa phải giống hệt: `source_id, repo, ref, channel, pinned, title, url, path, lines,
   version, heading_path, excerpt`;
2. **nội dung** — `text` (trường mới của `get_chunk`) so với `excerpt` của hit C/D: bằng nhau / `excerpt`
   là tiền tố của `text` / ngược lại;
3. **đối chiếu nguồn** — `text` so với chính range dòng tại pin:
   `git -C research/cache/git/<source> show <pin>:<path>` rồi cắt `lines[a-1:b]`; đếm cả trường hợp chỉ
   lệch ký tự trắng ở biên (đầu/cuối range).

### 4.2 Bảng G2

| # | case | cite_id | khớp nội dung? | chi tiết | dẫn chứng raw |
|---|---|---|---|---|---|
| 01 | G2_01 | `ardupilot_wiki#f8ab2e4e432c8a39` | khớp | `text` = đúng 490 ký tự của range nguồn (khớp từng byte); `excerpt` C/D là tiền tố | `raw/G2_01.json`:27 (text), :23 (isError); gốc `raw/C10.json`:42 |
| 02 | G2_02 | `expresslrs#fe280216f9d9cd5e` | khớp | `text` = đúng 1625 ký tự của range nguồn (khớp từng byte); `excerpt` C/D là tiền tố | `raw/G2_02.json`:27 (text), :23 (isError); gốc `raw/C4.json`:142 |
| 03 | G2_03 | `expresslrs_docs#9b82e6e086b6b0f5` | khớp | `text` = đúng 514 ký tự của range nguồn (khớp từng byte); `excerpt` C/D là tiền tố | `raw/G2_03.json`:27 (text), :23 (isError); gốc `raw/C12.json`:42 |
| 04 | G2_04 | `edgetx#a2f1bf22a7c437f0` | khớp | `text` = range nguồn trừ 1 ký tự xuống dòng cuối; `excerpt` C/D là tiền tố | `raw/G2_04.json`:27 (text), :23 (isError); gốc `raw/C2.json`:67 |
| 05 | G2_05 | `ardupilot#0adec6354cbdf85d` | khớp | `text` = đúng 2993 ký tự của range nguồn (khớp từng byte); `excerpt` C/D là tiền tố | `raw/G2_05.json`:27 (text), :23 (isError); gốc `raw/C2.json`:142 |
| 06 | G2_06 | `ardupilot#84faa083fcae8409` | khớp | `text` = range nguồn trừ 1 dòng trống đầu; `excerpt` C/D là tiền tố | `raw/G2_06.json`:27 (text), :23 (isError); gốc `raw/C3.json`:94 |
| 07 | G2_07 | `ardupilot_wiki#c2593dacde94604e` | khớp | `text` = đúng 551 ký tự của range nguồn (khớp từng byte); `excerpt` C/D là tiền tố | `raw/G2_07.json`:27 (text), :23 (isError); gốc `raw/C11.json`:67 |
| 08 | G2_08 | `expresslrs#fbe624b4e6902251` | khớp | `text` = đúng 1746 ký tự của range nguồn (khớp từng byte); `excerpt` C/D là tiền tố | `raw/G2_08.json`:27 (text), :23 (isError); gốc `raw/C2.json`:92 |
| 09 | G2_09 | `ardupilot#52da62b485d7dbdd` | khớp | `text` = đúng 904 ký tự của range nguồn (khớp từng byte); `excerpt` C/D là tiền tố | `raw/G2_09.json`:27 (text), :23 (isError); gốc `raw/C7.json`:67 |
| 10 | G2_10 | `crsf_spec#90c2ac349451f6c9` | khớp | `text` = đúng 491 ký tự của range nguồn (khớp từng byte); `excerpt` C/D là tiền tố | `raw/G2_10.json`:27 (text), :23 (isError); gốc `raw/C1.json`:92 |
| 11 | G2_11 | `ardupilot#d2d15d1ffa0b19e9` | khớp | `text` = range nguồn trừ 1 dòng trống đầu; `excerpt` C/D là tiền tố | `raw/G2_11.json`:27 (text), :23 (isError); gốc `raw/C2.json`:42 |
| 12 | G2_12 | `ardupilot#0566f786fd5d051a` | khớp | `text` = đúng 2982 ký tự của range nguồn (khớp từng byte); `excerpt` C/D là tiền tố | `raw/G2_12.json`:27 (text), :23 (isError); gốc `raw/D4.json`:44 |
| 13 | G2_13 | `ardupilot#9db38568cd9df5e4` | khớp | `text` = đúng 1144 ký tự của range nguồn (khớp từng byte); `excerpt` C/D là tiền tố | `raw/G2_13.json`:27 (text), :23 (isError); gốc `raw/C7.json`:42 |
| 14 | G2_14 | `ardupilot#bca71e018b58cdcb` | khớp | `text` = đúng 265 ký tự của range nguồn (khớp từng byte); `excerpt` C/D là tiền tố | `raw/G2_14.json`:27 (text), :23 (isError); gốc `raw/C1.json`:142 |
| 15 | G2_15 | `edgetx#d3d997571493b805` | khớp | `text` = range nguồn trừ 1 ký tự xuống dòng cuối; `excerpt` C/D là tiền tố | `raw/G2_15.json`:27 (text), :23 (isError); gốc `raw/C4.json`:42 |
| 16 | G2_16 | `ardupilot_wiki#f504ee227905786f` | khớp | `text` = đúng 627 ký tự của range nguồn (khớp từng byte); `excerpt` C/D là tiền tố | `raw/G2_16.json`:27 (text), :23 (isError); gốc `raw/D3.json`:67 |
| 17 | G2_17 | `ardupilot#ade96649dd76f1f9` | khớp | `text` = đúng 2220 ký tự của range nguồn (khớp từng byte); `excerpt` C/D là tiền tố | `raw/G2_17.json`:27 (text), :23 (isError); gốc `raw/C8.json`:142 |
| 18 | G2_18 | `ardupilot_wiki#a13e972632dda146` | khớp | `text` = đúng 512 ký tự của range nguồn (khớp từng byte); `excerpt` C/D là tiền tố | `raw/G2_18.json`:27 (text), :23 (isError); gốc `raw/D3.json`:42 |
| 19 | G2_19 | `ardupilot#9345259ec64dd06e` | khớp | `text` = đúng 1546 ký tự của range nguồn (khớp từng byte); `excerpt` C/D là tiền tố | `raw/G2_19.json`:27 (text), :23 (isError); gốc `raw/C1.json`:117 |
| 20 | G2_20 | `expresslrs_docs#34d87707cbd6f1b9` | khớp | `text` = đúng 826 ký tự của range nguồn (khớp từng byte); `excerpt` C/D là tiền tố | `raw/G2_20.json`:27 (text), :23 (isError); gốc `raw/C12.json`:92 |

### 4.3 Tổng hợp G2

- `isError`: **20/20** `false`; `transport_error`: **20/20** `null`; `duration_ms` 8.2–11.6 ms.
- Metadata: **20/20 không lệch khóa nào** (`field_diff` = `[]`), gồm cả `url`, `lines`, `path`, `ref`.
- Nội dung: **20/20 khớp**. Cụ thể: **6/20** `text == excerpt` (những hit mà excerpt C/D không bị cắt);
  **20/20** `excerpt` C/D là **tiền tố** của `text` (get_chunk trả nhiều hơn excerpt — đúng như
  `raw/_meta/tools_list.json:74` mô tả "Returns the citation object plus the verbatim `text`" và
  `tools_list.json:5` "Read more of one hit with get_chunk(cite_id)").
- Đối chiếu nguồn tại pin: **16/20** `text` khớp **từng byte** với range dòng; **4/20** lệch đúng **1 ký tự
  trắng ở biên** và phần còn lại giống hệt: `G2_04` và `G2_15` thiếu 1 dòng trống ở **cuối** range
  (`block_tail` có thêm `\n`), `G2_06` và `G2_11` thiếu 1 dòng trống ở **đầu** range
  (`block = "\n" + text`) — đúng cùng hiện tượng biên của **G-01**, không mất nội dung.
- **Không có mismatch nào** giữa `get_chunk` và hit C/D mà nó sinh ra.

**Ví dụ một cặp đã so (G2_02 — `expresslrs#fe280216f9d9cd5e`, 1 trong 14 cặp excerpt bị cắt 600):**

- Hit C/D gốc: `raw/C4.json:162` — `"excerpt"` dài 600 ký tự, kết thúc bằng
  `…\n\n    const uint32_t mspPayloadLen = ` (bị cắt giữa dòng).
- `get_chunk`: `raw/G2_02.json:27` — `"text"` dài **1625** ký tự, bắt đầu **giống hệt** excerpt rồi tiếp
  `getPayloadLen(data, mspVersion);…` đến hết hàm. So với nguồn tại pin
  (`git show a9d4a9cb5b5687c4c9d7e9e7fbdf44ad93651da6:src/lib/CRSF2MSP/msp2crsf.cpp`, dòng 92–133):
  `text == block` (1625/1625 ký tự). Vậy `get_chunk` trả **đủ** range, không phải bản cắt.

---

## 5. Danh sách phát hiện (mỗi mục một vấn đề, không gộp)

### F-01 — `F_MB`: query 1 MB bị SQLite từ chối bằng lỗi thô, không có kiểm tra độ dài và không có thông báo độ dài

**Bằng chứng thô**

- `raw/F_MB.json:20` `"duration_ms": 37.1`
- `raw/F_MB.json:23` `"isError": true`
- `raw/F_MB.json:27` nguyên văn:
  `Error executing tool search_docs: LIKE or GLOB pattern too complex`
- `raw/F_MB.json:30` `"structuredContent": null`
- `raw/F_MB.json:6` `"query"` = chuỗi **1 000 000** ký tự `A` (script đếm `len(query) = 1000000` và
  `query == "A"*1000000`), i.e. đúng 1 MB như chú thích `raw/F_MB.json:3` "1 MB query: no crash, <10s".
- Không crash: `raw/summary.tsv:84-111` (28 case sau F_MB, gồm `A1_RERUN_CORRECTED` … `G2_20`) đều có
  `duration_ms` và `transport_error=False`; `raw/_meta/server-stderr.log:4-222` = 110 `CallToolRequest`,
  không có dòng lỗi.

**Vì sao là lỗi (TOOL SAI)**

1. Hợp đồng tool **không** giới hạn độ dài: `raw/_meta/tools_list.json:8-11` khai báo
   `"query": {"title": "Query", "type": "string"}` — không có `maxLength`/`pattern`; mô tả tool
   (`tools_list.json:5`) chỉ giới hạn *excerpt* 600 ký tự, không nói gì về *query*. Vậy 1 MB là đầu vào
   hợp lệ theo chính khai báo của server.
2. Message là chuỗi lỗi engine kiểu SQLite (`LIKE or GLOB pattern too complex`), tức query đã được ghép
   vào một mẫu `LIKE`/`GLOB` và chỉ hỏng ở tầng engine, **sau** khi đã vào handler — không phải bị từ chối
   ở tầng kiểm tra đầu vào. (Suy luận từ message; người kiểm không đọc `src/` để giữ tính hộp đen.)
3. Message trả về là **chuỗi lỗi engine SQLite thô** ("LIKE or GLOB pattern too complex"), làm lộ chi tiết
   cài đặt (SQLite + cơ chế LIKE/GLOB) và **không hướng dẫn** người dùng (không nói "query too long",
   không nói giới hạn). `structuredContent` null (`raw/F_MB.json:30`) nên client chỉ có một câu tiếng Anh
   không có cấu trúc.

**Không phải crash**: MCP trả một response hợp lệ với `isError: true` (kênh lỗi chuẩn của MCP), tiến trình
sống và phục vụ 28 case tiếp theo. Đây là lỗi chất lượng đầu vào, không phải sự cố vận hành.

**Phân loại Luật 3: TOOL SAI.** (Không phải "KỲ VỌNG CỦA TÔI SAI" vì kỳ vọng đóng băng chỉ đòi
không crash/không treo/không lộ path — tool thỏa cả ba; nhưng hành vi lỗi vẫn là lỗi của tool so với
hợp đồng của chính nó.)

### G-01 — 2/20 excerpt không bắt đầu tại `line_start` khi `line_start` là dòng trống

**Bằng chứng thô**

- Mục 6: `raw/_meta/g1_sample.json:133` `"cite_id": "ardupilot#84faa083fcae8409"`,
  `:142` `path` = `libraries/AP_RCProtocol/AP_RCProtocol_CRSF.cpp`, `:143-146` `lines` = `[476, 544]`;
  excerpt bắt đầu bằng `"    return rc_active;\n}\n\n/*\n  decode channels from the standard 11bit…"`
  (`g1_sample.json:153`).
  `git -C research/cache/git/ardupilot show fb773567896014da007bca58358704d4a0d8516f:libraries/AP_RCProtocol/AP_RCProtocol_CRSF.cpp`
  → dòng 476 là **dòng rỗng**; nội dung `"    return rc_active;"` nằm ở dòng 477.
- Mục 11: `raw/_meta/g1_sample.json:258` `"cite_id": "ardupilot#d2d15d1ffa0b19e9"`, `:267` `path`,
  `:268-271` `lines` = `[689, 714]`; dòng 689 của cùng file là **dòng rỗng**; excerpt
  (`g1_sample.json:278`) bắt đầu bằng `"    return true;\n}\n\n// change the bootstrap baud rate…"`
  = nội dung dòng 690.
- Kiểm định lượng: `block.lstrip("\n")[:600] == excerpt` → **True** cho cả hai
  (2475/2476 và 742/743 ký tự). Vậy excerpt = nội dung range **sau khi bỏ dòng trống đầu**, cắt 600 ký tự.

**Phân loại Luật 3: KHÔNG XÁC ĐỊNH.**

- Không mất nội dung: dòng bị bỏ là dòng trống; excerpt vẫn nằm trọn trong `[line_start, line_end]` và mọi
  ký tự của nó đều tồn tại trong range.
- `tools/list` định nghĩa excerpt là "a **verbatim excerpt** of at most 600 characters"
  (`raw/_meta/tools_list.json:5`) — một excerpt bắt đầu ở dòng 477 vẫn "verbatim"; tài liệu **không** hứa
  "excerpt bắt đầu đúng tại line_start".
- Nhưng nếu hiểu "đúng dòng" của `tests/blackbox_cases.md:71` là "ký tự đầu tiên của excerpt nằm đúng tại
  `line_start`" thì hai mục này lệch **1 dòng trống**. Không có căn cứ trong file đóng băng để khẳng định
  tool sai; cũng không đủ để khẳng định kỳ vọng của tôi đúng. Vì vậy: **KHÔNG XÁC ĐỊNH**, kèm mô tả định
  lượng ở trên để người đọc tự quyết.

---

## 6. Quan sát (không phải lỗi, không đưa vào danh sách phát hiện)

1. **14/20 excerpt bị cắt 600 ký tự** (range 627–2993 ký tự). Đây là hành vi **được tài liệu hóa**:
   `raw/_meta/tools_list.json:5` "a verbatim excerpt of at most 600 characters", và G2 chứng minh
   `get_chunk` trả **đủ** range (16/20 khớp từng byte với nguồn). Vì vậy không phải lỗi; nhưng khi đọc
   citation, excerpt **không** đại diện toàn bộ `line_start..line_end` — cần `get_chunk` để đọc hết.
2. **13/20 URL dùng tag thay vì SHA**: `Copter-4.7.2` ×9, `4.1.0` ×2, `v2.12.5` ×2. Kỳ vọng đóng băng
   cho phép "SHA/tag" (`tests/blackbox_cases.md:71`), và tại thời điểm kiểm cả 13 tag resolve đúng pin
   SHA trong object store (`raw/_meta/env.json:5,8,9`). Rủi ro tiềm ẩn (không phải lỗi hiện tại): tag có
   thể bị di chuyển upstream, còn SHA thì bất biến.
3. **F_SQLI / F_NEAR / F_FIND_STAR / F_FIND_QUOTE trả `found: true` với input rác** — không vi phạm
   tiêu chí F (chỉ đòi không crash/treo/lộ path); hành vi là "coi input là văn bản", không phải lỗi SQL.
   Bằng chứng index không hề hấn: các case `G2_*` chạy **sau** vẫn trả nội dung thật
   (`raw/summary.tsv:92-111`).
4. **F_CHUNK_PATH echo lại `'../../x'`** trong error message (`raw/F_CHUNK_PATH.json:27`). Đó là input của
   client được nhắc lại, **không** phải đường dẫn trên máy chủ (không match mẫu path tuyệt đối nào).

---

## 7. Những gì KHÔNG kiểm được (và lý do)

1. **Exit code / PID / uptime của tiến trình server**: file raw không lưu; không được phép chạy lại case.
   "Crash" trong báo cáo này được đánh giá **gián tiếp** bằng: (a) các case sau vẫn có response,
   (b) `transport_error` null, (c) `server-stderr.log` có đủ 110 `CallToolRequest` và không có
   `Traceback/ERROR`. Không có bằng chứng trực tiếp nào về việc tiến trình có bị restart giữa chừng.
2. **Ngưỡng chính xác của query gây lỗi LIKE**: chỉ có **một** điểm dữ liệu (1 MB) trong raw; không được
   gọi server để thử 10 KB / 60 KB. Suy đoán từ message SQLite (giới hạn pattern ~50 000 byte) **không**
   được xác nhận thực nghiệm — không đưa vào kết luận.
3. **Toàn bộ 72 citation**: G1 chỉ yêu cầu 20 mẫu seed 7; 52 citation còn lại của pool C/D không được kiểm
   nội dung. (Script xác nhận 20/20 mẫu có trong 72 cite_id duy nhất, không trùng.)
4. **Tag upstream**: object store offline là ảnh tĩnh; không kiểm được tag trên GitHub hiện có còn trỏ
   đúng commit hay không.
5. **`get_chunk` với `context_lines > 0`**: 20/20 case G2 gọi mặc định (`context_lines` không có trong
   `arguments`, xem `raw/G2_01.json:5-7`), nên nhánh "thêm chunk lân cận" của tool không được kiểm.
6. **Hành vi khi 2 request đồng thời / khi tiến trình bị kill giữa request**: ngoài phạm vi 110 case đã đóng băng.

---

## 8. Tái lập

```powershell
cd D:\Skill_tulan\ardupilot-research-mcp
$env:PYTHONUTF8 = '1'
python scripts\verify_fg.py f       # bảng + chi tiết F
python scripts\verify_fg.py g1      # bảng + chi tiết G1 (gọi git show tại pin)
python scripts\verify_fg.py g2      # bảng + chi tiết G2
python scripts\verify_fg.py md      # 3 bảng markdown dùng trong file này
python scripts\verify_fg.py render  # ghi lại 3 bảng vào FG.md tại 3 marker
python scripts\verify_fg.py selfcheck
# selfcheck: mọi "raw/<file>.json:<dòng>" trong FG.md phải nằm trong phạm vi file,
# 30 trích dẫn nguyên văn phải khớp đúng dòng, 12+20+20 dòng bảng, 0 marker sót.
```

Script chỉ đọc `docs/blackbox/raw/**` + `research/cache/git/**`; không import code của dự án, không mở
socket, không gọi MCP server. Ngày chạy: 2026-10-25. Môi trường ghi trong `raw/_meta/env.json:2-3`
(Python 3.11.9, Windows-10-10.0.19045-SP0), commit `raw/_meta/env.json:23` = `4010ad53c68c13f020caa7d700d37d6e883ce205`.
