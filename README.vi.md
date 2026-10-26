# ardupilot-research-mcp, bản tiếng Việt

MCP server chạy trên máy bạn, trả lời câu hỏi về ArduPilot, ExpressLRS, EdgeTX, CRSF và MAVLink từ
một kho tài liệu đã ghim phiên bản, kèm trích dẫn kiểm tra lại được bằng `git show`.

Server chạy như tiến trình stdio. Không có URL, không port, không API key, không daemon, không
database server. Client MCP gọi `python -m ardupilot_research_mcp.server` và nói chuyện qua stdio.
Lúc trả lời, server chỉ đọc một file là `data/index.sqlite`. Mạng chỉ dùng một lần để dựng index.

Server không arm, không flash, không xoá, không ghi tham số, không mở cổng serial và không nói
chuyện với drone. Câu trả lời hoặc có `cite_id`, permalink ghim, đúng khoảng dòng và đoạn trích
nguyên văn, hoặc nói `found:false`.

```
python -m ardupilot_research_mcp.server     # MCP stdio, 14 tool
python -m pytest -q                         # 191 passed
```

Repo: `github.com/TOKGS/Drone_MCP`. Package `ardupilot-research-mcp` v0.1.0, Python 3.10 trở lên.
Bản tiếng Anh: [`README.md`](README.md).

## Đây là gì

Đây là công cụ tra cứu cho người viết hoặc debug code ArduPilot, đấu dây flight controller, giải mã
frame CRSF, đọc `hwdef.dat`, kiểm tra file Intel HEX, hoặc hỏi vì sao một tham số không còn ở tag
phát hành. Kho dữ liệu gồm mã firmware, wiki, XML MAVLink, source và docs ExpressLRS, EdgeTX và spec
CRSF, mỗi nguồn ở một ref đã ghim.

Server không có đường ghi. Không tool nào đổi trạng thái, và câu hỏi không có trong kho trả
`found:false` thay vì đoán.

| Bạn hỏi | Bạn nhận |
|---|---|
| `lookup_param("RC_OPTIONS")` | khối `@Param` khai báo, các bit `@Bitmask`, `default_raw` và `default` đã quy (32), kèm permalink ghim |
| `decode_bitmask("RC_OPTIONS", "0x2000")` | `bit 13 SET: Use 420kbaud for ELRS protocol`, đọc từ header ghim |
| `mavlink_message("HEARTBEAT")` | msgid 0, danh sách field, CRC extra, trích dẫn vào `common.xml` |
| `decode_crsf_frame("C8 18 16 …")` | 16 kênh × 11 bit, trạng thái CRC8, micro giây theo macro `TICKS_TO_US`, số byte đuôi cụt |
| `check_intelhex_line(":1001…40")` | trạng thái checksum, record type, byte dữ liệu |
| `troubleshoot("tắt failsafe để nó khỏi báo")` | từ chối, nêu vì sao nguy hiểm và đường an toàn, không đưa cách tắt failsafe |
| `search_docs("giá bitcoin hôm nay")` | `found:false` kèm ghi chú ngoài phạm vi |

## Cam kết

| Cam kết | Được kiểm bởi |
|---|---|
| Chỉ đọc: cả 14 tool mang `readOnlyHint=true, idempotentHint=true, openWorldHint=false` | `server.py`, `tests/test_offline.py` |
| Offline lúc trả lời: chỉ đọc `data/index.sqlite`, không import module mạng ngoài `ingest/` | `tests/test_distil.py` (xoá corpus, tool vẫn trả lời), `tests/test_offline.py` |
| Đoạn trích là thật: text của chunk là lát cắt byte của file ghim, kiểm trên cả 86 262 chunk | `scripts/fidelity_scan.py`, `research/audit_git.py` |
| Ghim, không dùng branch: URL trỏ tag hoặc commit SHA đầy đủ | `research/verify_citations.py` (0 URL chưa ghim) |
| Không bịa tên: thiếu tham số, board hay message thì trả `found:false` kèm ứng viên thật, và có `renamed_hint` khi release notes ghi việc đổi tên | `tests/test_params.py`, `tests/test_mavlink_board.py` |
| An toàn trước: yêu cầu tắt hoặc che kiểm tra arm, failsafe, fence bị từ chối kèm đường an toàn, thủ tục phần cứng có dòng `Props off for bench tests. SITL before hardware.` | `safety.py`, `safety_rules.yaml`, `tests/safety_cases_v2.yaml` |
| Đoạn trích là dữ liệu: mọi citation mang `untrusted: true` và không bao giờ được làm theo | `cite.py` |
| Không lỗi câm: input quá dài trả lỗi `max_length`, exception lạ trả `{"found":false,"error":"internal error","error_id":"…"}` với chi tiết chỉ ở stderr | `tools/_base.py`, `tests/test_query.py` |

## Cài đặt

Yêu cầu:

- Python 3.10 trở lên kèm `pip` (đã test trên 3.11.9).
- Khoảng 3 GB đĩa trống cho build: corpus 115 MB, `data/index.sqlite` 182 MB và cache tải về 2,7 GB.
  Cache nằm trong gitignore, xoá được sau khi build xong vì phần trả lời chỉ cần index.
- Mạng một lần cho build.

```powershell
git clone https://github.com/TOKGS/Drone_MCP.git ardupilot-research-mcp
cd ardupilot-research-mcp
python -m venv .venv; .\.venv\Scripts\Activate.ps1
pip install -e .
```

```bash
# Linux hoặc WSL
python3 -m venv .venv && . .venv/bin/activate && pip install -e .
```

Phụ thuộc chỉ có `mcp==1.30.0` và `pyyaml`; `pytest` nằm trong extra dev. SDK bị ghim vì bề mặt
schema của tool đã được kiểm đúng trên phiên bản đó (`docs/research-notes.md`).

## Dựng index

```powershell
python -m research.fetch tags        # phân giải tag Copter-X.Y.Z mới nhất bằng git ls-remote, loại beta và rc
python -m research.fetch download    # tải archive tại đúng pin, không tốn quota tìm kiếm
python -m research.extract           # corpus đã lọc vào data/corpus
python -m ardupilot_research_mcp.ingest.cli --all --rebuild-index
python -m research.build_params      # @Param, @Bitmask và @Default vào bảng params
python -m research.build_mavlink     # XML MAVLink vào bảng message và enum
python -m ardupilot_research_mcp.ingest.cli --verify
# tùy chọn, chỉ cho semantic retrieval: python -m research.build_vectors   (khoảng 68 phút)
```

Mất khoảng năm phút và tạo `data/index.sqlite` 182 MB: 7 356 document thành 86 262 chunk, 5 089
tham số, 397 message MAVLink và 2 367 enum entry.
Stage vector là tùy chọn: thêm 63 MB và khoảng một giờ CPU, mọi thứ khác vẫn chạy khi không có nó.

`--resume` là mặc định, bỏ qua file đã index theo hash. `--rebuild-index` tạo lại file SQLite.

## Chạy server

```powershell
python -m ardupilot_research_mcp.server     # Ctrl+C để dừng, không mở port nào
```

Vì nói chuyện bằng stdio, server không in gì ra và chờ client MCP. Muốn thử một tool mà không cần
client:

```powershell
$env:PYTHONPATH = "src"
python -c "import sys; sys.path.insert(0,'src'); from ardupilot_research_mcp.tools.lookup_param import lookup_param; import json; print(json.dumps(lookup_param('RC_OPTIONS'), ensure_ascii=False, indent=1)[:1500])"
```

Vài câu hỏi đầu tiên:

```
lookup_param("ARMING_SKIPCHK")
decode_bitmask("RC_OPTIONS", "0x2000")
decode_crsf_frame("C81816E0031FF8C0073EF0810F7CE0031FF8C0073EF0810F7CAD")
check_intelhex_line(":10010000214601360121470136007EFE09D2190140")
troubleshoot("what does FS_THR_ENABLE do, and which value means disabled?")
```

## 14 tool

Mỗi tool là một hàm thuần trong `src/ardupilot_research_mcp/tools/<tên>.py`. Guard chung giới hạn 60
lần gọi mỗi phút, chặn input quá dài trước khi chạm SQLite, cắt response ở ba excerpt mỗi nguồn, 600
ký tự mỗi excerpt và 24 KB tổng, và biến exception lạ thành payload `internal error` kèm `error_id`.

| Tool | Tham số | Trả về |
|---|---|---|
| `search_docs` | `query` (tối đa 2000), `scope` (`all`, `docs`, `code`, `protocol`, `dev`, `local`), `version`, `tier_max`, `limit` | tài liệu đã xếp hạng kèm citation, `scope_notes`, `confidence`, `note` |
| `get_chunk` | `cite_id`, `context_lines` | chunk và các dòng lân cận, cùng đối tượng citation |
| `lookup_param` | `name_or_pattern`, `vehicle` (mặc định ArduCopter), `version` | `params[]` có `display_name`, `enum_values`, `bitmask`, `default_raw`, `default`, `default_resolved`, `renamed_hint`, citation |
| `decode_bitmask` | `param`, `value` là số hoặc tên bit | số thành tên bit, hoặc tên bit thành số, đối chiếu với `@Bitmask` |
| `find_source` | `symbol_or_file`, `repo`, `version` | đường dẫn định nghĩa, permalink ghim, citation |
| `board_info` | `board_name`, `hal` | dữ kiện `hwdef.dat`: MCU, `SERIAL_ORDER`, define RC, gợi ý DMA, `included_files` |
| `mavlink_message` | `name_or_id` (`HEARTBEAT`, `0`, hoặc tên enum) | field, CRC extra, giá trị enum, citation vào `common.xml` |
| `troubleshoot` | `symptom`, `context` | chẩn đoán có bằng chứng, hoặc từ chối kèm `dangerous`, `refused_as_fix`, `message`, `safe_path`, `why_dangerous` |
| `get_script` | `topic` | một script đầy đủ trong `examples/`, `cite_id` và lệnh chạy |
| `decode_crsf_frame` | `hex` (tối đa 4096 ký tự) | frame, `frames_found`, `all_crc_valid` (`null` khi không có frame), micro giây từng kênh, `truncated_tail_bytes` |
| `check_intelhex_line` | `line` (tối đa 600) | start code, byte count, trạng thái checksum, record type |
| `parse_ihex_summary` | `path` trong `data/` (tối đa 1024) | số record theo type, byte dữ liệu, khoảng địa chỉ, có EOF hay không |
| `list_sources` | không | từng nguồn kèm pin, tier, license, số document |
| `index_status` | không | số đếm sources, documents, chunks, params, kích thước index, lần ingest cuối, ghi chú offline |

Giá trị `scope`: `docs` là wiki và docs ExpressLRS, `code` là mã firmware, `protocol` là MAVLink và
CRSF, `dev` là wiki dev ArduPilot, `local` là file board của bạn và không bao giờ lẫn vào số recall,
`all` là mọi thứ trừ `local`.

## Hợp đồng trích dẫn

```jsonc
{
  "cite_id": "ardupilot#1a2b3c4d5e6f7a8b",      // <source_id>#<hash16>
  "source_id": "ardupilot",
  "repo": "ArduPilot/ardupilot",
  "ref": "Copter-4.7.2",                        // tag hoặc commit SHA đầy đủ
  "channel": "stable",                          // stable | snapshot | local
  "unreleased": false,
  "pinned": true,
  "url": "https://github.com/ArduPilot/ardupilot/blob/Copter-4.7.2/libraries/RC_Channel/RC_Channels_VarInfo.h#L92-L97",
  "path": "libraries/RC_Channel/RC_Channels_VarInfo.h",
  "lines": [92, 97],
  "excerpt": "…lát cắt nguyên văn, tối đa 600 ký tự…",
  "version": "Copter-4.7.2 (2026-10-20)",
  "ingested_at": "2026-10-25T20:13:33+0700",
  "tier": "T1",
  "license": "GPL-3.0",
  "untrusted": true
}
```

`cite_id` sinh từ nội dung: `sha256(source_id | path | line_start | line_end | sha256(text))` cắt 16
ký tự hex. Index lại cùng text cho cùng id, đổi text thì đổi id.

`get_chunk(cite_id)` trả đúng text mà citation đã hứa. Blackbox đã kiểm 20 trên 20 với
`field_diff = 0`.

Pin bằng tag cho `channel:"stable"`. Pin bằng commit cho `channel:"snapshot"` kèm
`unreleased:true`. Lớp local cho `channel:"local"`, `pinned:false` và `url:null`.

## Nguồn và pin

`sources.yaml` giữ repo, ref (tag hoặc SHA, không bao giờ là branch), tier, license và glob include.
`research.fetch tags` phân giải tag `Copter-X.Y.Z` mới nhất bằng `git ls-remote --tags --refs`, loại
beta và rc, và không có số phát hành nào bị viết cứng trong `src/`
(`tests/test_offline.py::test_no_hardcoded_release_version_outside_tests`).

| Nguồn | Repo | Pin | Tier | License |
|---|---|---|---|---|
| `ardupilot` | ArduPilot/ardupilot | `Copter-4.7.2` tại `fb77356789…` | T1 | GPL-3.0 |
| `ardupilot_wiki` | ArduPilot/ardupilot_wiki | `828de1f225dace34b482e63abaab15d25b2b1732` | T1 | CC-BY-SA-3.0 |
| `mavlink` | mavlink/mavlink | `eec8824212c1fe8c5d8f5181fcfdef54ee219b63` | T1 | chưa công bố |
| `expresslrs` | ExpressLRS/ExpressLRS | `4.1.0` tại `a9d4a9cb5b5687c4c9d7e9e7fbdf44ad93651da6` | T2 | GPL-3.0 |
| `expresslrs_docs` | ExpressLRS/ExpressLRS | `5ed656b6ebc7a38b6012297cf40fe5bc87232bed` | T2 | GPL-3.0 |
| `edgetx` | EdgeTX/edgetx | `v2.12.5` tại `0ebe2e98b2085e2251ad6773b26c8a7ab8dd3e99` | T2 | GPL-2.0 |
| `crsf_spec` | bản mirror spec CRSF | `a73f7dc5386e5b8744aa4a23b3af5354ee0d4c92` | T2 | CC-BY-SA-4.0 |
| `local-project` | file của bạn | `local` | T3 | user-owned |

Index hiện có 7 nguồn, 7 356 document và 86 262 chunk trong 182,3 MB. `list_sources` cho số theo
từng nguồn. License đọc từ file license của từng archive (`docs/license-notes.md`). Corpus không
bao giờ được commit: `data/` và `research/cache/` nằm trong gitignore.

## Bản ArduPilot 4.6

Drone còn chạy firmware 4.6 nhận khai báo sai từ pin 4.7: `ARMING_CHECK` trả `found:false` vì 4.7
đổi tên thành `ARMING_SKIPCHK`, và `ATC_ACCEL_*` thành `ATC_ACC_*`. `sources-4.6.yaml` ghim
`Copter-4.6.2` và dựng vào `data/4.6` (index 169,0 MB, 79 558 chunk, 4 356 tham số,
`verify: PASS`, recall@5 trên heldout_v3 là 0,933). Chọn bằng `ARM_SOURCES` và `ARM_DATA_DIR`;
`.mcp.json.example` có entry server thứ hai. Cách dựng, thời gian đo được và phần chưa kiểm chứng:
[docs/variant-4.6.md](docs/variant-4.6.md).

## Tham số

`lookup_param` trả lời từ metadata `@Param`, `@Bitmask` và `@Default` trong source ghim.

- 5 089 tên tham số từ 2 070 khối `@Param`. Tên đầy đủ ghép theo chuỗi `@Group` và `@Path` của bản
  pin, nên `@Param: 1_PROTOCOL` trong `AP_SerialManager.cpp` cộng tiền tố `SERIAL` thành
  `SERIAL1_PROTOCOL`. Các họ instance mở đúng: `RC1..RC16`, `SERIAL1..8`, `BATT` và `BATTA`, `INS`,
  `INS2`, `INS3`, `COMPASS2/3`, `OSD1..5`. Không có dòng trùng: 0 dòng trùng
  `(path, line_start, prefix)`.
- `default_raw` là đối số nguyên văn của `@Default:`, có ở 4 703 trong 5 089 dòng. Nó chỉ thành số
  khi là literal, biểu thức bit, hoặc đúng một `#define` trong corpus. Cách đó quy được 3 003 dòng
  và để nguyên 1 700 dòng, số không quy được thì báo ra chứ không đoán. Ví dụ: `FS_THR_ENABLE` cho
  1 từ `FS_THR_ENABLED_ALWAYS_RTL`, `FS_THR_VALUE` cho 975, `RC_OPTIONS` cho 32, `ARMING_SKIPCHK`
  cho 0. `LOG_BITMASK` giữ `default_raw=DEFAULT_LOG_BITMASK` với `default_resolved:false`.
- Mọi citation trỏ đúng khối của chính tham số. Cả 5 089 dòng được kiểm bằng máy để excerpt chứa
  `@Param:<hậu tố>` và khoảng dòng bao trùm nó, với 0 vi phạm
  (`scripts/check_param_citations.py`). Trước khi sửa, 3 891 trong 5 089 citation trỏ sang khối bên
  cạnh.
- Việc đổi tên được báo. `ARMING_CHECK` trả `found:false` kèm
  `renamed_hint{new:"ARMING_SKIPCHK", path:"ArduCopter/ReleaseNotes.txt"}`. `WPNAV_SPEED` trả
  `found:false` không gợi ý, vì release notes không ghi việc đổi tên đó.
- Độ phủ được đo trên file dùng thật. Trong 1 440 tên duy nhất mà
  `Tools/autotest/default_params/*.param` và `Tools/Frame_params/*.param` dùng ở bản pin, 739 tên
  (51,3 %) được tìm thấy. Phần lớn số còn lại thuộc frame của xe khác, phân loại trong
  `docs/fix/A-names.txt`.
- Các ca không quy được nằm trong `docs/fix/A-unresolved.txt`: 509 khối unresolved và 142 khối
  unlinked.

## Chính sách an toàn

Server giải thích hệ thống an toàn và không trình bày việc tắt nó như một cách sửa.

Luật nằm trong `src/ardupilot_research_mcp/safety_rules.yaml` dưới dạng các danh sách
`disable_verbs`, `safety_objects`, `safety_params`, `value_patterns`, `info_markers`,
`hardware_markers` và `dangerous_excerpt`. Việc so khớp chạy trên text đã chuẩn hoá, nên `tắt
failsafe`, `tat failsafe` và `turn the failsafe off` trúng cùng một luật.

Một yêu cầu bị từ chối khi động từ tắt nhắm vào đối tượng an toàn, hoặc khi tham số an toàn đi với
mẫu đặt về 0, kể cả khi viết dạng câu hỏi. Đối tượng an toàn chỉ đi với dấu hiệu hỏi thông tin thì
đi nhánh giải thích, nêu kiểm tra đó làm gì kèm bằng chứng.

Khi từ chối, payload có `dangerous:true`, `refused_as_fix:true`, `message`, `why_dangerous` và
`safe_path`, trong đó `safe_path` nói phải đọc đúng thông báo pre-arm, sửa nguyên nhân đó và kiểm
bằng SITL trước. Citation chỉ giữ những đoạn giải thích mục đích của kiểm tra; đoạn chứa công thức
tắt bị lọc, và nếu không còn đoạn an toàn nào thì payload có `citations: []` kèm `citations_note`.

Dòng `Props off for bench tests. SITL before hardware.` xuất hiện khi cổng an toàn kích hoạt hoặc
khi chủ đề là thủ tục bench, không xuất hiện ở chỗ khác.

Đo trên cây hiện tại: 20 cách nói bypass (tiếng Việt có dấu, không dấu, lẫn Anh Việt, và tiếng Anh)
cho 0 false negative, 10 câu hỏi thông tin lành tính cho 0 false positive, và mục E của blackbox
run2 pass 15 trên 15. Run1 lọt ba câu.

Server sẽ không in `ARMING_CHECK=0`, `ARMING_SKIPCHK≠0`, "force arm", "disable the failsafe or
fence", hay một bước bench mà thiếu dòng props-off.

## Cách truy xuất

Query được chuẩn hoá hoa thường và dấu, rồi mở rộng bằng từ điển Việt Anh khớp theo token, nên `bit`
khớp đúng từ chứ không khớp chuỗi con trong `bitcoin`. Stopword bị bỏ.

Tiếp theo là cổng neo ngữ liệu. Từ nội dung xuất hiện ở dưới ba document, và không phải symbol
`snake_case` có trong index, thì không đủ neo cho query, và query không neo được trả `found:false`
kèm ghi chú ngoài phạm vi.

Ứng viên lấy từ FTS5 trên trường text đã chưng cất gồm từ trong path, heading path và thân đã bỏ
markup, cộng một lượt khớp literal cho tên symbol và tên tham số chính xác, xếp theo BM25.

Điểm tính theo document: chunk tốt nhất thắng, cộng điểm cho token trong path và heading, thưởng khi
heading chứa đủ token của query, và trừ điểm cho model chỉ dành cho simulator dưới `libraries/SITL/`.

Sau đó là ghi chú phạm vi và confidence. Tên sản phẩm ngoài kho như `PX4`, số phiên bản mà không pin
nào có, và độ trùng khớp yếu với ba kết quả đầu đều thêm một mục `scope_notes` và hạ `confidence`.

Chỉ đến bước này chunk mới thành citation, với hash nội dung, URL ghim, khoảng dòng và excerpt.
`chunks.text` giữ nguyên văn byte cho citation, `chunks.distilled` chỉ phục vụ FTS, nhờ vậy trang
wiki nhiều markup vẫn khớp câu hỏi văn xuôi mà không làm sai đoạn trích.

## Cấu hình

Sáu biến môi trường, mặc định lấy theo checkout:

| Biến | Mặc định | Ý nghĩa |
|---|---|---|
| `ARM_REPO_ROOT` | checkout chứa `src/` | nơi có `sources.yaml`, `glossary.vi-en.yaml`, `scope.yaml` |
| `ARM_DATA_DIR` | `<repo>/data` | nơi có `index.sqlite`, `corpus/`, `local/` |
| `GOVERNOR_HOME` | `<repo>/research` | nơi có sổ cái quota |
| `ARM_SOURCES` | `<repo>/sources.yaml` | bộ pin khác, ví dụ `sources-4.6.yaml` |
| `ARM_DENSE` | không đặt, tắt | `1` bật rerank ngữ nghĩa tùy chọn (xem bên dưới) |
| `ARM_MODEL_DIR` | `<data>/models/multilingual-e5-small` | thư mục model ONNX và tokenizer |

Vì index và ledger phân giải từ các biến này, bạn giữ được nhiều bản độc lập trên cùng máy, ví dụ
mỗi worktree một bản:

```powershell
$env:ARM_REPO_ROOT = "D:\work\ardupilot-research-mcp"
$env:ARM_DATA_DIR  = "D:\work\ardupilot-research-mcp\data"
$env:GOVERNOR_HOME = "D:\work\ardupilot-research-mcp\research"
```

Thiếu index thì mọi tool trả
`{"found":false,"error":"index not built: run ardupilot-research-ingest --all"}`.

## Quota

Nguồn tính phí (Firecrawl, Exa, web search, GitHub API) chỉ được tiêu qua `research/governor.py`,
theo vòng reserve, call, record. Governor giữ sổ cái SQLite WAL (`research/ledger.sqlite`) với file
lock, cửa sổ trượt, 20 % headroom, khoảng cách tối thiểu giữa các lần gọi, ngân sách theo provider,
cache-first, xử lý `Retry-After`, backoff luỹ thừa, circuit breaker, và ghi `STATE.md` khi cạn ngân
sách.

```powershell
python -m research.governor status
python -m research.governor reserve --provider firecrawl --endpoint scrape --query "https://…"
python -m research.governor record  --id 42 --status ok --http-code 200 --result-sha abc123
python -m research.governor export-report
```

Sổ cái của index này ghi `calls=88, cost_units=32.0`, trong đó firecrawl 0, exa 0 và web_search 0.
Corpus lấy bằng `git ls-remote` và archive codeload nên không tốn đơn vị tìm kiếm nào. Build lại từ
cache nóng cũng không tốn gì.

## Đăng ký client

Lệnh server luôn là:

```
python -m ardupilot_research_mcp.server
```

Nó cần `PYTHONPATH=<repo>/src` hoặc cài editable. Thay `D:\Skill_tulan\ardupilot-research-mcp` bằng
đường dẫn checkout của bạn.

Đã kiểm ngoài sandbox: Claude Code 2.1.308 kết nối được, liệt kê đủ 14 tool dưới dạng
`mcp__ardupilot-research__*`, `claude mcp list` báo `√ Connected` với đăng ký user scope; lượt model
ở đó dừng ở `"Not logged in · Please run /login"`, là đăng nhập của client chứ không phải server.

OpenCode 2.1.3 với model miễn phí `opencode/deepseek-v4.1-flash-free` đã chạy trọn một lượt: model
gọi `tools["ardupilot-research"].lookup_param({name_or_pattern:"RC_OPTIONS"})`, nhận `default: 32`
với `cite_id ardupilot#11fb2497e2a89d95`, và trả lời `32`. Transcript:
`docs/blackbox/h/opencode_stream.jsonl`; cấu hình ở `docs/client-setup.md` mục 7.

Codex chưa từng được chạy. JSON init thô của hai client đã chạy nằm ở `docs/client-setup.md`.

`.mcp.json` ở project scope cần một lần duyệt tương tác. Phiên `-p` headless thấy nó ở trạng thái
`pending` với 0 tool, và đó là thứ run1 ghi thành `status: failed`. Đặt
`enableAllProjectMcpServers: true` trong `.claude/settings.json` hay `.claude/settings.local.json`
không đổi được trạng thái đó trên bản 2.1.308.

### Claude Code

```powershell
# user scope: Connected, không cần duyệt tay
claude mcp add --scope user ardupilot-research `
  --env PYTHONPATH=D:\Skill_tulan\ardupilot-research-mcp\src `
  --env ARM_REPO_ROOT=D:\Skill_tulan\ardupilot-research-mcp `
  --env ARM_DATA_DIR=D:\Skill_tulan\ardupilot-research-mcp\data `
  -- python -m ardupilot_research_mcp.server
claude mcp list                     # kỳ vọng: ardupilot-research … √ Connected

# project scope: ghi ra .mcp.json, sau đó duyệt một lần trong TUI
claude mcp add --scope project ardupilot-research …            # rồi mở `claude` và approve
# hoặc bỏ bước duyệt bằng cách truyền file tường minh:
claude -p "<câu hỏi>" --mcp-config .\.mcp.json --strict-mcp-config
```

File project trông như sau:

```json
{
  "mcpServers": {
    "ardupilot-research": {
      "type": "stdio",
      "command": "python",
      "args": ["-m", "ardupilot_research_mcp.server"],
      "env": {
        "PYTHONPATH": "D:\\Skill_tulan\\ardupilot-research-mcp\\src",
        "ARM_REPO_ROOT": "D:\\Skill_tulan\\ardupilot-research-mcp",
        "ARM_DATA_DIR": "D:\\Skill_tulan\\ardupilot-research-mcp\\data"
      }
    }
  }
}
```

### OpenCode

`opencode.jsonc`. Server local nằm dưới `mcp`, `type: "local"`, `command` là mảng, chép từ
`sst/opencode`, `packages/web/src/content/docs/mcp-servers.mdx`:

```jsonc
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "ardupilot-research": {
      "type": "local",
      "command": ["python", "-m", "ardupilot_research_mcp.server"],
      "enabled": true,
      "environment": {
        "PYTHONPATH": "D:\\Skill_tulan\\ardupilot-research-mcp\\src",
        "ARM_DATA_DIR": "D:\\Skill_tulan\\ardupilot-research-mcp\\data"
      }
    }
  }
}
```

### Codex

Tên khoá dưới đây chưa kiểm chứng. Tài liệu cấu hình của Codex redirect tới trang đăng nhập nên không
có gì được đoán:

```toml
[mcp_servers.ardupilot-research]
command = "python"
args = ["-m", "ardupilot_research_mcp.server"]
env = { PYTHONPATH = 'D:\Skill_tulan\ardupilot-research-mcp\src', ARM_DATA_DIR = 'D:\Skill_tulan\ardupilot-research-mcp\data' }
```

### Chứng minh nó chạy

```powershell
claude mcp list
# ardupilot-research: python -m ardupilot_research_mcp.server - √ Connected
claude -p "hi" --mcp-config .\.mcp.json --strict-mcp-config --output-format stream-json --verbose 2>&1 |
  Select-Object -First 1
# …"mcp_servers":[{"name":"ardupilot-research","status":"connected"}],
#  "tools":[… "mcp__ardupilot-research__lookup_param" … đủ 14]
```

Rồi hỏi: *"tra RC_OPTIONS và cho biết bit nào bật ELRS 420kbaud"*. Câu trả lời đúng trích
`libraries/RC_Channel/RC_Channels_VarInfo.h`, dòng 92 đến 97, và gọi tên
`bit 13: Use 420kbaud for ELRS protocol`. Câu trả lời sai không có `cite_id`, hoặc trỏ vào
`AP_Arming`. Nếu client báo server failed, `docs/client-setup.md` mục 4 đi qua python trên PATH,
`PYTHONPATH`, cwd, biến môi trường và bọc `cmd /c`.

## Test và cổng kiểm

```powershell
python -m pytest -q                                     # 191 passed
python scripts\check_traceability.py                    # yêu cầu, test, kết quả, failing=0
python scripts\fidelity_scan.py                         # 86 262 chunk, 0 mismatch, PASS
python scripts\check_param_citations.py                 # 5 089 tham số, 0 vi phạm
python scripts\check_readmes.py                         # hai README: không còn dấu hiệu văn AI, số liệu khớp
python scripts\bench.py                                 # p50/p95 của search theo ngân sách
python -m research.verify_citations                     # khoảng dòng và URL ghim, PASS
python -m research.audit_safety                         # sáu input an toàn bắt buộc
python -m research.eval_retrieval --set tests/golden.yaml --aggregate-only
python -m research.eval_retrieval --set tests/heldout_v3.yaml --aggregate-only
python scripts\mutation_check.py                        # điểm mutation
```

Đo lần cuối trên cây đã merge với index dựng lại từ đầu:

| Cổng | Kết quả |
|---|---|
| `pytest -q` | 191 passed, 1 skipped |
| `fidelity_scan.py` | 86 262 chunk, 0 mismatch, PASS |
| `check_param_citations.py` | 5 089 kiểm, 0 vi phạm |
| `check_traceability.py` | 22 yêu cầu, failing=0 |
| `verify_citations` | PASS, 0 URL chưa ghim |
| bộ an toàn, 30 câu | 0 false negative, 0 false positive |
| golden, dev và tinh chỉnh được | recall@5 1.000, P@1 0.767, MRR 0.859 |
| held-out v3, blind và đóng băng | recall@5 0.933, P@1 0.833, MRR 0.868 |
| mutation | 1.000, giết 14 trên 14 mutant tính điểm, 1 mutant tương đương được tách riêng |

Mutant M12 được xếp là tương đương thay vì tính điểm: mệnh đề "Value 0 ... disable"
trong bộ lọc excerpt trùng tác dụng với các mẫu `dangerous_excerpt` trong `safety_rules.yaml`,
nên không test nào phân biệt được nó với bản gốc.
| blackbox, 108 case đóng băng | run2 92 pass / 16 fail, run3 93 / 15 sau khi sửa chọn chunk, 0 hồi quy, 3 lần chạy payload giống nhau |
| tất định của khâu chấm | 5 script chạy hai lần, output byte-identical |
| `check_readmes.py` | PASS |
| `bench.py` | search p50 58,5 ms, p95 186 ms, ngân sách 400 ms, PASS |

`tests/conftest.py` reset guard tốc độ giữa các test. Guard sản phẩm vẫn giữ 60 lần gọi mỗi phút.

Cả `data/index.sqlite` và `data/corpus` đều nằm trong gitignore, nên clone mới tự thích nghi thay vì
fail: module nào cần index hoặc corpus thì tự skip. Có đủ cả hai thì bộ test chạy 191 passed và 1
skipped; test bị skip là test thoát khỏi thư mục bằng symlink trên tài khoản Windows này.

## Chất lượng đo được

| Tập | Là gì | recall@5 | P@1 | MRR |
|---|---|---|---|---|
| `tests/golden.yaml` | 30 câu dev, tinh chỉnh được, không phải bằng chứng | 1.000 | 0.767 | 0.859 |
| `tests/heldout_v3.yaml` | 30 câu blind, mỗi câu một đáp án bảo vệ được, SHA-256 đóng băng trước khi chạy | 0.933 | 0.833 | 0.868 |
| `tests/heldout_locked.yaml` | tập đóng băng đầu tiên, nhiều kỳ vọng sai dữ kiện | 0.433 | 0.300 | 0.334 |
| `tests/heldout_v2.yaml` | blind nhưng nhập nhằng | 0.733 | 0.400 | 0.513 |

Tập công bằng là v3 (`docs/eval-heldout-v3.md`). v1 và v2 giữ lại để trung thực và không dùng để
tính điểm. Hash ở `docs/heldout*.sha256`, evaluator từ chối chạy nếu tập bị đổi.

Bộ đo hiện tại là eval v4: 125 câu viết từ bằng chứng corpus, chia 53 câu dev và 72 câu held-out
đóng băng (`docs/eval-v4.md`). Kết quả held-out, mỗi cấu hình một dòng:

| cấu hình | recall@5 | P@1 | MRR | chunk-hit@5 | negative-pass |
|---|---|---|---|---|---|
| baseline Phase 1 | 0.692 | 0.369 | 0.493 | 0.369 | 0.571 |
| Rung 1 từ khóa, bản mặc định | 0.723 | 0.323 | 0.475 | 0.369 | 0.571 |
| Rung 2 rerank ngữ nghĩa, tùy chọn | 0.692 | 0.277 | 0.439 | 0.354 | 0.571 |

Điểm yếu là tập tiếng Việt: recall@5 0.516 so với 0.906 của tiếng Anh ở bản mặc định. Theo nhóm và
theo ngôn ngữ: `docs/upgrade/rung1.md` và `docs/upgrade/rung2.md`.

Một người kiểm thử độc lập đóng băng 108 case mức tool (`tests/blackbox_cases.md`, SHA-256
`1b53e69…dcaf27`), chạy qua một phiên stdio và viết `docs/blackbox/REPORT.md`, kết quả 80 pass và 28
fail. Sau vòng sửa lỗi trong `docs/FIX_REPORT.md`, đúng bộ case đó chạy lại vào `docs/blackbox/run2/`:
92 pass, 16 fail, không case nào từ pass thành fail, 12 case được sửa.

Sau khi sửa bước chọn chunk, bộ đó chạy lần thứ ba, ba lần liên tiếp: 93 pass, 15 fail, vẫn không hồi
quy, và cả 110 payload giống nhau giữa ba lần. Bảng điểm và 17 payload khác run2 nằm ở
`docs/blackbox/run3/comparison.md`.

15 case còn lại chia thành 5 lỗi tool và 10 case có kỳ vọng đóng băng sai (một chuỗi hex thiếu
nibble, tham số không tồn tại ở tag, và những kỳ vọng coi `source_id` như phần của path). Bảng
so sánh 108 dòng kèm output thô ở `docs/blackbox/run2/comparison.md`.

Năm script chấm điểm cũng được chạy hai lần trên cùng raw và cho kết quả byte-identical, nên verdict
92 trên 16 không phụ thuộc thứ tự chạy hay thời điểm (`docs/blackbox/run2/determinism.md`).
Việc chọn chunk trong document thắng giờ ưu tiên khớp nguyên từ và chunk không có heading hẹp
hơn, nên C1 từ chỗ gần trúng thành trích đúng đoạn `0xD5`.

## Tùy chọn: semantic retrieval

Một retriever ONNX e5-small có thể rerank danh sách ứng viên của BM25. Nó tắt mặc định: đo trên eval
v4 đóng băng thì nó không thắng được cách xếp hạng thường (`docs/upgrade/rung2.md`).

```powershell
pip install -e ".[embeddings]"      # onnxruntime, tokenizers, numpy
python -m research.build_vectors    # 86 262 chunk, 63 MB, khoảng 68 phút trên 8 core
$env:ARM_DENSE = "1"                # bật tùy chọn; không đặt thì chỉ dùng BM25
```

Model là `intfloat/multilingual-e5-small` (ONNX, 448.5 MB, MIT, xem `docs/license-notes.md`), đặt ở
`data/models/multilingual-e5-small/`; đổi `ARM_MODEL_DIR` nếu để chỗ khác. Index tăng 63 MB và lần
search đầu tiên của mỗi tiến trình mất khoảng 7 giây để nạp vector.

Đánh đổi đo được trên held-out v4: recall@5 0.692 so với 0.723 và MRR 0.439 so với 0.475 của bản mặc
định, nên chỉ bật khi câu hỏi của bạn thiên về ngữ nghĩa hơn là tên định danh. Thiếu extras, model
hoặc bảng `chunk_vectors` thì luôn quay về BM25; đặt `ARM_DENSE=1` mà thiếu tài nguyên sẽ in một
cảnh báo nêu lý do, và `index_status` báo
`dense: {state: "requested-but-unavailable", unavailable_reason: ...}`.

## Tái lập

```powershell
python -m venv .venv; .\.venv\Scripts\Activate.ps1; pip install -e .
python -m research.build_all --gates         # fetch, extract, ingest, params, mavlink, rồi các cổng
python -m research.eval_retrieval --set tests/heldout_v3.yaml --aggregate-only
python scripts\smoke_stdio.py               # cần pipe stdio, chạy ngoài sandbox
python -m research.build_all --prune-cache   # tuỳ chọn: xoá archive đã tải
```

`build_all` chạy từng stage thành tiến trình riêng và dừng ở lỗi đầu tiên, nên thông báo lỗi chỉ ra
stage. `--dry-run` in lệnh mà không chạy, `--prune-cache` xoá 2,7 GB archive khi index đã có.

## Bố cục

```
sources.yaml                     corpus ghim: repo, ref, tier, license, glob include và exclude
glossary.vi-en.yaml              từ điển Việt Anh cho query, khớp theo token
scope.yaml                       tên sản phẩm ngoài kho, ngưỡng khớp yếu
pyproject.toml                   mcp==1.30.0 và pyyaml, console script
src/ardupilot_research_mcp/
  server.py                      chỉ phần nối MCP: stdio, ToolAnnotations, 14 tool
  config.py                      đường dẫn repo, data và ledger
  db.py                          schema SQLite và FTS5 external-content
  query.py                       cổng neo, BM25 và tìm theo identifier, ghi chú phạm vi, xếp hạng
  cite.py                        cite_id, URL ghim, excerpt 600 ký tự
  safety.py                      cổng từ chối và giải thích
  safety_rules.yaml              chính các luật
  guard.py                       giới hạn tốc độ và cắt response
  tools/<tên>.py                 mỗi tool một hàm thuần, chỉ đọc
  decoders/                      CRSF frame và Intel HEX, chỉ stdlib
  ingest/                        package duy nhất được chạm mạng
research/                        fetch, extract, build_params, build_mavlink, governor, audit, eval
scripts/                         smoke, tool matrix, fidelity, check, mutation, blackbox
examples/                        4 script chạy được, kèm cite_id
tests/                           unit, protocol, an toàn, offline, golden, held-out đóng băng
docs/                            design, license, eval, FIX_REPORT, client-setup, blackbox
```

`data/` chứa corpus, index và file `local-project` của bạn. Nó và `research/cache/` đều nằm trong
gitignore, nên repo chứa công thức chứ không chứa vài GB source upstream.

## Xử lý sự cố

| Hiện tượng | Nguyên nhân và cách sửa |
|---|---|
| `index not built: run ardupilot-research-ingest --all` | thiếu `data/index.sqlite`, dựng index |
| `lookup_param` trả `found:false` cho tham số có thật | library đó ngoài include list, hoặc tên thuộc xe khác; payload liệt kê ứng viên thật và có `renamed_hint` khi release notes ghi việc đổi tên |
| `default: null` kèm `default_raw` | chuỗi macro không có một cách quy duy nhất, nên báo ra chứ không đoán (`default_resolved:false`) |
| `found:false` kèm "no anchor in the indexed corpus" | kho không dùng những từ đó |
| `hex string too long` hoặc `query too long (max N chars)` | giới hạn input: query 2000, tên 128, path 1024, dòng Intel HEX 600, hex CRSF 4096 |
| `internal error` kèm `error_id` | lỗi thật, traceback ở stderr theo id đó, thu stderr và báo lại |
| `smoke_stdio.py` ném `PermissionError: [WinError 5]` | phiên chặn pipe stdio, chạy ngoài sandbox |
| `git: schannel: SEC_E_NO_CREDENTIALS` trên Windows | `git -c http.sslBackend=openssl -c http.sslVerify=false …` |
| client báo server failed mà không nêu lý do | `docs/client-setup.md` mục 4 đi qua python trên PATH, `PYTHONPATH`, cwd, biến môi trường và `cmd /c`; xem thêm ghi chú duyệt ở trên |
| điểm held-out thấp | đọc `docs/eval-heldout.md` và `docs/eval-heldout-v2.md`, hai tập đó đã công bố là không công bằng hoặc nhập nhằng |

## Hạn chế và điều chưa kiểm chứng

Đã kiểm trên Claude Code 2.1.308 ngoài sandbox: server kết nối được, client liệt kê 14 tool, và
`claude mcp list` báo `√ Connected` với đăng ký user scope.

Chưa kiểm chứng:

- Codex. Máy này không cài, tên khoá stdio chưa xác nhận.
- Tool call do model phát ra trong Claude Code, vì phiên đó chưa đăng nhập. OpenCode đã có một lượt
  như vậy trên hồ sơ.

Hạn chế đã biết:

- Xếp hạng trượt 3 case đóng băng (`C4`, `C10`, `C11`). Đúng file có trong index nhưng không lọt
  top năm với cách diễn đạt đó. `C1` đã sửa: chunk thắng giờ là định nghĩa (`0xD5`), không phải đoạn
  Command frame (`0xBA`) dùng chung các từ đó.
- Hai tham số `SERIAL1_PROTOCOL` và `LOG_BITMASK` tìm thấy nhưng default vẫn unresolved vì chuỗi
  macro không có một giá trị duy nhất. Case đòi default bằng số cho chúng thì fail.
- 509 khối `@Param` unresolved và 142 khối unlinked nằm trong `docs/fix/A-unresolved.txt`.
- `A4_100K` trả lỗi validation của schema (`isError`, content rỗng) thay vì payload `{found:false}`,
  vì `decode_crsf_frame` dùng pydantic `max_length` còn các tool khác validate trong wrapper. Cả hai
  là lỗi rõ ràng, chỉ khác hình dạng.
- `board_info` chỉ theo một cấp `include` trong `hwdef.dat`.
- Chưa ingest nguồn T2 issue và PR, và T3 forum. Danh sách nguồn là bảy repo đã ghim.
- `local-project` index file của bạn, không pin và không URL, và không bao giờ lẫn vào số recall.
- `heldout_locked` được 0.433, dưới mức 0.8. Tập đó đã công bố là không công bằng và không dùng làm
  bằng chứng.
- Test link escape (`tests/test_hardening.py`) bị skip trên account không tạo được symlink thư mục,
  nên khả năng thoát qua junction chưa được chứng minh trên máy này.

## Giấy phép và nguồn gốc

Code của server là MIT, trong file `LICENSE` (và khai trong `pyproject.toml`).

Corpus không được phân phối lại. `data/` và `research/cache/` nằm trong gitignore, excerpt trả về bị
cắt ở 600 ký tự, mang license của nguồn và URL ghim, nên một đoạn trích vẫn truy được về file gốc.

Theo từng nguồn, đọc từ file license của archive (`docs/license-notes.md`): ardupilot GPL-3.0,
ardupilot_wiki CC-BY-SA-3.0, ExpressLRS GPL-3.0, ExpressLRS Docs GPL-3.0, EdgeTX GPL-2.0, spec CRSF
CC-BY-SA-4.0, XML MAVLink chưa công bố và giữ nguyên nhãn đó theo quyết định rõ ràng.

Binary, ảnh, font, archive, file `.hex` và `.apj` không vào corpus, và `LICENSE`, `COPYING` hay
`README` của từng nguồn được ép include để nguồn gốc đi cùng nội dung.

## Trạng thái

v0.1.0, lượt hoàn chỉnh đầu tiên, 2026-10-25.

- 14 tool qua stdio, chỉ đọc và offline, 191 test, 86 262 chunk không lệch fidelity.
- Bảng tham số dựng lại từ metadata ghim: 230 thành 5 089 tham số, vi phạm citation 3 891 thành 0,
  default 0 thành 4 703 raw với 3 003 quy được.
- Cổng an toàn viết lại thành dữ liệu với khớp song ngữ đã chuẩn hoá dấu: false negative từ 3 trên 11
  xuống 0 trên 20, false positive giữ 0 trên 10, và citation khi từ chối không còn chứa công thức tắt.
- Giới hạn input và che lỗi nội bộ cho mọi tool, từ điển khớp theo token, cổng neo ngữ liệu để câu
  ngoài kho trả `found:false`, và trừ điểm code simulator khi xếp hạng.
- `decode_crsf_frame` báo `frames_found`, trả `all_crc_valid:null` khi không có frame, báo
  `truncated_tail_bytes`, và quy micro giây bằng phép chia cắt về 0 kiểu C, nên tick 172 cho 988.
- Chạy lại blackbox độc lập trên 108 case đóng băng: 92 pass ở run2, 93 ở run3, không hồi quy, ba
  lần chạy cho payload giống nhau.
- Wiring client đã chứng minh trong hai client thật: Claude Code kết nối và liệt kê 14 tool (user
  scope báo `√ Connected`), và một phiên OpenCode với model miễn phí đã gọi `lookup_param` rồi trả lời
  từ citation.
- Mutation harness trỏ lại đúng code hiện tại, một mutant tương đương được phân loại thay vì tính
  điểm, và bộ lọc stopword đã có test.
- `research.build_all` gom build về một lối vào, `research.extract` không còn fail ở lớp local, và
  `scripts/bench.py` canh độ trễ.
- CI chạy unit test, cổng README và traceability trên Windows lẫn Ubuntu; một job hàng tuần dựng
  index rồi chạy các cổng đã công bố.
- Thêm `LICENSE`, và `.mcp.json` trở lại là file theo máy (chỉ commit `.mcp.json.example`).

Sổ lỗi, quyết định và chi phí ở `docs/FIX_REPORT.md`, nhật ký từng lỗi ở `docs/fix/`.

Việc nên làm tiếp: xếp hạng bốn case truy xuất còn lại mà không tinh chỉnh theo từng câu, quy thêm
default từ macro, ingest nguồn T2 và T3, và hoàn tất một phiên client đã đăng nhập để có tool call do
model phát ra trên hồ sơ.
