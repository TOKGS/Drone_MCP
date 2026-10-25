# ardupilot-research-mcp — bản tiếng Việt

**MCP server chạy NỘI BỘ (local), chỉ đọc, trả lời câu hỏi kỹ thuật ArduPilot / ExpressLRS / EdgeTX /
CRSF / MAVLink từ một kho tài liệu đã ghim phiên bản — mọi câu trả lời có trích dẫn kiểm chứng được
bằng máy.**

Server không bao giờ arm, flash, xoá, ghi tham số, mở cổng serial hay nói chuyện với drone; và
**không gọi mạng lúc trả lời**. Mỗi câu trả lời hoặc có `cite_id` + permalink + đúng khoảng dòng +
đoạn trích nguyên văn, hoặc nói thẳng `found:false`.

```
$ python -m ardupilot_research_mcp.server          # MCP stdio, 14 tool
$ python -m pytest -q                              # 134 passed
```

Repo: `github.com/TOKGS/Drone_MCP` · package `ardupilot-research-mcp` v0.1.0 · Python ≥ 3.10
Bản tiếng Anh: [`README.md`](README.md)

---

> ## TL;DR — đây là MCP **local**, không phải dịch vụ cloud
>
> Không deploy ở đâu cả: **không URL, không port, không HTTP, không API key, không daemon, không
> Docker, không database server**. Client MCP (Claude Code / OpenCode / Codex) tự spawn tiến trình
> `python -m ardupilot_research_mcp.server` trên máy bạn và nói chuyện qua **stdio**. Lúc trả lời,
> server chỉ đọc đúng một file: `data/index.sqlite`. Mạng chỉ dùng **một lần** để dựng index.
>
> | Bước | Lệnh | Cần gì |
> |---|---|---|
> | 1 · cài (vài giây) | `pip install -e .` | Python ≥ 3.10; kéo `mcp==1.30.0` + `pyyaml` |
> | 2 · dựng index (~5 phút, 1 lần) | `fetch tags` → `fetch download` → `ingest --all --rebuild-index` → `build_params` → `build_mavlink` | mạng + **~3 GB đĩa** (corpus 115 MB, index 182 MB, cache tải về 2,7 GB) |
> | 3 · đăng ký client | mục [7](#7-đăng-ký-client), ví dụ `claude mcp add --scope user ardupilot-research …` | không |
> | 4 · kiểm chứng | `claude mcp list` → `√ Connected`, hoặc `python -m pytest -q` → `134 passed` | không |
> | 5 · dùng | hỏi *"tra RC_OPTIONS và cho biết bit nào bật ELRS 420kbaud"* | không — **offline** |
>
> Chuyển máy: chỉ cần `data/index.sqlite` (cùng bản checkout) là phần trả lời chạy được, không cần
> mạng. Windows và Linux/WSL đều chạy; ghi chú riêng theo OS nằm ở mục [15](#15-xử-lý-sự-cố).

## Mục lục

1. [Đây là gì / không phải gì](#1-đây-là-gì--không-phải-gì)
2. [Cam kết](#2-cam-kết)
3. [Yêu cầu & cài đặt](#3-yêu-cầu--cài-đặt)
4. [Dựng index](#4-dựng-index-lần-duy-nhất-đi-mạng)
5. [Chạy server](#5-chạy-server)
6. [14 tool](#6-14-tool)
7. [Đăng ký client](#7-đăng-ký-client)
8. [Hợp đồng trích dẫn](#8-hợp-đồng-trích-dẫn)
9. [Nguồn & phiên bản ghim](#9-nguồn--phiên-bản-ghim)
10. [Tham số](#10-tham-số)
11. [Chính sách an toàn](#11-chính-sách-an-toàn)
12. [Cách truy xuất](#12-cách-truy-xuất)
13. [Cấu hình](#13-cấu-hình)
14. [Quota & sổ cái](#14-quota--sổ-cái)
15. [Xử lý sự cố](#15-xử-lý-sự-cố)
16. [Test & cổng kiểm](#16-test--cổng-kiểm)
17. [Chất lượng đo được](#17-chất-lượng-đo-được)
18. [Tái lập toàn bộ](#18-tái-lập-toàn-bộ)
19. [Hạn chế & điều chưa kiểm chứng](#19-hạn-chế--điều-chưa-kiểm-chứng)
20. [Giấy phép & nguồn gốc](#20-giấy-phép--nguồn-gốc)
21. [Bố cục repo](#21-bố-cục-repo)
22. [Trạng thái & thay đổi](#22-trạng-thái--thay-đổi)

---

## 1. Đây là gì / không phải gì

**Là** server tri thức cho người viết/debug firmware ArduPilot, đấu dây flight controller, giải mã
frame CRSF, đọc `hwdef.dat`, kiểm tra file Intel HEX, hoặc hỏi tại sao một tham số không còn tồn tại ở
tag phát hành. Kho dữ liệu là **chính mã nguồn firmware, wiki, XML MAVLink, source/docs ExpressLRS,
EdgeTX và spec CRSF ở phiên bản đã ghim** — không phải trí nhớ của model.

**Không phải** kênh điều khiển, công cụ ghi tham số, công cụ flash firmware, bản thay thế Mission
Planner, hay máy tìm kiếm tổng quát. Không có tool nào thay đổi dữ liệu, và không có cơ chế "chắc là
đúng" khi kho không có câu trả lời.

| Bạn hỏi | Bạn nhận |
|---|---|
| `lookup_param("RC_OPTIONS")` | khối `@Param` khai báo, các bit `@Bitmask`, `default_raw` → `default` đã quy (32), permalink ghim |
| `decode_bitmask("RC_OPTIONS", "0x2000")` | `bit 13 SET: Use 420kbaud for ELRS protocol` — lấy từ header ghim |
| `mavlink_message("HEARTBEAT")` | msgid 0, danh sách field, CRC extra, trích dẫn `common.xml` |
| `decode_crsf_frame("C8 18 16 …")` | 16 kênh × 11 bit, CRC8 hợp lệ hay không, µs theo macro `TICKS_TO_US` của spec, thông tin đuôi cụt |
| `check_intelhex_line(":1001…40")` | checksum đúng/sai, record type, byte dữ liệu |
| `troubleshoot("tắt failsafe để nó khỏi báo")` | **từ chối** + vì sao nguy hiểm + đường an toàn, không đưa công thức tắt |
| `search_docs("giá bitcoin hôm nay")` | `found:false` + ghi chú ngoài phạm vi — không trả 5 kết quả trông có vẻ đúng |

## 2. Cam kết

| # | Cam kết | Được bảo đảm bởi |
|---|---|---|
| 1 | **Chỉ đọc.** 14/14 tool mang `readOnlyHint=true, idempotentHint=true, openWorldHint=false`; không tồn tại đường ghi trong `src/`. | `server.py`, `tests/test_offline.py` |
| 2 | **Offline lúc trả lời.** Chỉ đọc `data/index.sqlite`; không đọc file corpus, không import module mạng ngoài `ingest/`. | `tests/test_distil.py` (xoá corpus, tool vẫn trả lời), `tests/test_offline.py` |
| 3 | **Excerpt là thật.** Text của chunk là lát cắt byte của file ghim; quét toàn bộ 86 262 chunk với blob Git. | `scripts/fidelity_scan.py`, `research/audit_git.py` |
| 4 | **Ghim, không dùng branch.** URL trỏ tag hoặc commit SHA đầy đủ — không bao giờ `main`/`master`/`HEAD`. | `research/verify_citations.py` (0 URL chưa ghim) |
| 5 | **Không bịa tên.** Không có tham số/board/message → `found:false` kèm ứng viên thật; nếu release notes có ghi đổi tên thì trả `renamed_hint`. | `tests/test_params.py`, `tests/test_mavlink_board.py` |
| 6 | **An toàn trước.** Yêu cầu tắt/che kiểm tra arm, failsafe, fence, hoặc force-arm bị từ chối kèm đường an toàn; thủ tục phần cứng luôn có dòng `Props off for bench tests. SITL before hardware.` | `safety.py` + `safety_rules.yaml`, `tests/safety_cases_v2.yaml` |
| 7 | **Excerpt là dữ liệu, không phải mệnh lệnh.** Mọi citation mang `untrusted: true`; server không làm theo chỉ thị nằm trong kho. | `cite.py` |
| 8 | **Không lỗi câm.** Input quá dài → lỗi `max_length` rõ ràng; exception lạ → `{"found":false,"error":"internal error","error_id":"…"}`, chi tiết chỉ ra stderr. | `tools/_base.py`, `tests/test_query.py` |

## 3. Yêu cầu & cài đặt

Danh sách yêu cầu — hết:

- **Python ≥ 3.10** (`python -V`; dự án test trên 3.11.9) kèm `pip`.
- **~3 GB đĩa trống** cho build: corpus 115 MB + `data/index.sqlite` 182 MB + cache tải về 2,7 GB
  (`research/cache/`, đã gitignore, xoá được sau khi build xong — phần trả lời chỉ cần index).
- **Mạng một lần** cho khâu build. Không cài gì ra toàn hệ thống: không server, không daemon, không
  database engine, không API key — MCP đi qua stdio tới tiến trình con.

```powershell
git clone https://github.com/TOKGS/Drone_MCP.git ardupilot-research-mcp
cd ardupilot-research-mcp
python -m venv .venv; .\.venv\Scripts\Activate.ps1
pip install -e .
```

```bash
# Linux / WSL — y hệt, dùng python3
python3 -m venv .venv && . .venv/bin/activate && pip install -e .
```

Phụ thuộc chỉ có `mcp==1.30.0` và `pyyaml` (thêm `pytest` cho extra dev). SDK MCP bị ghim cứng vì bề
mặt schema của tool đã được kiểm đúng trên phiên bản đó (`docs/research-notes.md`).

## 4. Dựng index (lần duy nhất đi mạng)

```powershell
python -m research.fetch tags        # phân giải tag Copter-X.Y.Z mới nhất bằng git ls-remote (loại beta/rc)
python -m research.fetch download    # tải archive tại đúng pin (0 đơn vị quota tìm kiếm)
python -m research.extract           # corpus đã lọc -> data/corpus
python -m ardupilot_research_mcp.ingest.cli --all --rebuild-index
python -m research.build_params      # @Param / @Bitmask / @Default -> bảng params
python -m research.build_mavlink     # XML MAVLink -> bảng message/enum
python -m ardupilot_research_mcp.ingest.cli --verify
```

Kỳ vọng ≈ 5 phút và `data/index.sqlite` **≈ 182 MB**: 7 356 document → 86 262 chunk → 5 089 tham số →
397 message MAVLink / 2 367 enum entry.

`--resume` (mặc định) bỏ qua file đã index theo hash; `--rebuild-index` tạo lại file SQLite từ đầu.

## 5. Chạy server

Server là **một lệnh**, chạy như tiến trình stdio nên không in gì ra terminal và chờ message MCP —
việc gọi nó là của client:

```powershell
python -m ardupilot_research_mcp.server       # Ctrl+C để dừng; không mở port nào
```

Thử nhanh không cần client:

```powershell
$env:PYTHONPATH = "src"
python -c "import sys; sys.path.insert(0,'src'); from ardupilot_research_mcp.tools.lookup_param import lookup_param; import json; print(json.dumps(lookup_param('RC_OPTIONS'), ensure_ascii=False, indent=1)[:1500])"
```

Vài câu hỏi đầu tiên để thấy hợp đồng trích dẫn:

```
lookup_param("ARMING_SKIPCHK")
decode_bitmask("RC_OPTIONS", "0x2000")
decode_crsf_frame("C81816E0031FF8C0073EF0810F7CE0031FF8C0073EF0810F7CAD")
check_intelhex_line(":10010000214601360121470136007EFE09D2190140")
troubleshoot("what does FS_THR_ENABLE do, and which value means disabled?")
```

## 6. 14 tool

Mọi tool là hàm thuần trong `src/ardupilot_research_mcp/tools/<tên>.py`, bọc bởi guard chung:
(1) giới hạn 60 lần/phút, (2) chặn input quá dài **trước khi** chạm SQLite, (3) cắt response (≤ 3
excerpt mỗi nguồn, ≤ 600 ký tự mỗi excerpt, ≤ 24 KB tổng), (4) biến exception lạ thành `internal
error` + `error_id`.

| Tool | Tham số | Trả về |
|---|---|---|
| `search_docs` | `query` (≤ 2000), `scope` = `all\|docs\|code\|protocol\|dev\|local`, `version`, `tier_max`, `limit` | tài liệu xếp hạng kèm citation, `scope_notes`, `confidence`, `note` |
| `get_chunk` | `cite_id`, `context_lines` | đúng chunk + dòng lân cận, cùng đối tượng citation |
| `lookup_param` | `name_or_pattern`, `vehicle` (mặc định ArduCopter), `version` | `params[]` có `display_name`, `enum_values`, `bitmask`, `default_raw`, `default`, `default_resolved`, `renamed_hint`, citation |
| `decode_bitmask` | `param`, `value` (số hoặc tên bit) | số → tên bit, hoặc tên bit → số; đối chiếu độc lập với `@Bitmask` |
| `find_source` | `symbol_or_file`, `repo`, `version` | đường dẫn định nghĩa + permalink ghim + citation |
| `board_info` | `board_name`, `hal` | dữ kiện `hwdef.dat`: MCU, `SERIAL_ORDER`, define RC, gợi ý DMA, `included_files` |
| `mavlink_message` | `name_or_id` (`HEARTBEAT`, `0`, hoặc tên enum) | field, CRC extra, giá trị enum, citation `common.xml` |
| `troubleshoot` | `symptom`, `context` | chẩn đoán có bằng chứng **hoặc** từ chối kèm `dangerous`, `refused_as_fix`, `message`, `safe_path`, `why_dangerous` |
| `get_script` | `topic` | script mẫu chạy được trong `examples/`, `cite_id` và lệnh chạy |
| `decode_crsf_frame` | `hex` (≤ 4096 ký tự) | frame, `frames_found`, `all_crc_valid` (`null` khi 0 frame), µs từng kênh, `truncated_tail_bytes` |
| `check_intelhex_line` | `line` (≤ 600 ký tự) | start code, byte count, checksum đúng/sai, record type |
| `parse_ihex_summary` | `path` (chỉ trong `data/`, ≤ 1024) | đếm record theo type, byte dữ liệu, khoảng địa chỉ, có EOF hay không |
| `list_sources` | — | mọi nguồn kèm pin, tier, license, số document |
| `index_status` | — | số đếm (`sources/documents/chunks/params`), kích thước, lần ingest cuối, ghi chú offline |

`scope`: `docs` = wiki + docs ExpressLRS, `code` = mã firmware, `protocol` = MAVLink + CRSF,
`dev` = wiki dev ArduPilot, `local` = file board của riêng bạn (không bao giờ lẫn vào số recall),
`all` = mọi thứ trừ `local`.

## 7. Đăng ký client

Lệnh server luôn là `python -m ardupilot_research_mcp.server` (cần `PYTHONPATH=<repo>/src` hoặc cài
editable). Thay `D:\Skill_tulan\ardupilot-research-mcp` bằng đường dẫn checkout của bạn.

> **Đã kiểm chứng thật (Claude Code 2.1.308, ngoài sandbox):** server **kết nối được**, client liệt
> kê **đủ 14 tool** (`mcp__ardupilot-research__*`), `claude mcp list` báo `√ Connected`. Lượt model
> vẫn dừng ở `"Not logged in · Please run /login"` — lỗi đăng nhập của client, không phải server.
> **OpenCode và Codex chưa từng được chạy → UNVERIFIED.** Chi tiết + JSON thô:
> `docs/client-setup.md` §6.

### Claude Code

```powershell
# user scope — đã kiểm: `claude mcp list` báo √ Connected, không cần duyệt tay
claude mcp add --scope user ardupilot-research `
  --env PYTHONPATH=D:\Skill_tulan\ardupilot-research-mcp\src `
  --env ARM_REPO_ROOT=D:\Skill_tulan\ardupilot-research-mcp `
  --env ARM_DATA_DIR=D:\Skill_tulan\ardupilot-research-mcp\data `
  -- python -m ardupilot_research_mcp.server

# project scope — ghi ra .mcp.json, nhưng cần DUYỆT một lần bằng TUI
claude mcp add --scope project ardupilot-research …          # rồi mở `claude` và approve
# hoặc bỏ bước duyệt bằng cách truyền file tường minh:
claude -p "<câu hỏi>" --mcp-config .\.mcp.json --strict-mcp-config
```

### OpenCode

`opencode.jsonc` — server local nằm dưới `mcp`, `type: "local"`, `command` là **mảng**
(nguồn: `sst/opencode`, `packages/web/src/content/docs/mcp-servers.mdx`):

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

```toml
# ~/.codex/config.toml — tên khoá chưa kiểm chứng trên máy này: UNVERIFIED
[mcp_servers.ardupilot-research]
command = "python"
args = ["-m", "ardupilot_research_mcp.server"]
env = { PYTHONPATH = 'D:\Skill_tulan\ardupilot-research-mcp\src', ARM_DATA_DIR = 'D:\Skill_tulan\ardupilot-research-mcp\data' }
```

### Chứng minh nó chạy (2 phút, không tốn lượt model)

```powershell
claude mcp list
# ardupilot-research: python -m ardupilot_research_mcp.server - √ Connected
claude -p "hi" --mcp-config .\.mcp.json --strict-mcp-config --output-format stream-json --verbose 2>&1 |
  Select-Object -First 1
# …"mcp_servers":[{"name":"ardupilot-research","status":"connected"}],
#  "tools":[… "mcp__ardupilot-research__lookup_param" … đủ 14]
```

Rồi hỏi trong client: *"tra RC_OPTIONS và cho biết bit nào bật ELRS 420kbaud"*. Câu trả lời đúng trích
`libraries/RC_Channel/RC_Channels_VarInfo.h`, dòng 92–97, và gọi tên `bit 13 — Use 420kbaud for ELRS
protocol`. Câu trả lời sai không có `cite_id`, hoặc trỏ vào `AP_Arming`. Nếu client báo server
`failed`: `docs/client-setup.md` §4 đi qua python-on-PATH, `PYTHONPATH`, cwd, biến môi trường và bọc
`cmd /c` trên Windows.

## 8. Hợp đồng trích dẫn

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
  "excerpt": "…lát cắt nguyên văn, ≤ 600 ký tự…",
  "version": "Copter-4.7.2 (2026-10-20)",
  "ingested_at": "2026-10-25T20:13:33+0700",
  "tier": "T1",
  "license": "GPL-3.0",
  "untrusted": true
}
```

- `cite_id` **định địa chỉ theo nội dung**: `sha256(source_id | path | line_start | line_end |
  sha256(text))` cắt 16 hex. Index lại cùng text → cùng id; text đổi → id đổi.
- `get_chunk(cite_id)` trả đúng text mà citation đã hứa — blackbox kiểm 20/20, `field_diff = 0`.
- Quy tắc channel: pin **tag** → `stable`; pin **commit** → `snapshot` + `unreleased:true`;
  `local-project` → `channel:"local"`, `pinned:false`, `url:null`.
- Mọi excerpt bị cắt ở **600 ký tự** và mang cờ `untrusted:true`.

## 9. Nguồn & phiên bản ghim

`sources.yaml` là nguồn sự thật duy nhất: repo, ref (tag hoặc SHA — không bao giờ branch), tier,
license, glob include/exclude. `research.fetch tags` phân giải tag `Copter-X.Y.Z` mới nhất bằng
`git ls-remote --tags --refs` và loại beta/rc — không có số phiên bản nào bị viết cứng trong `src/`
(`tests/test_offline.py::test_no_hardcoded_release_version_outside_tests`).

| Nguồn | Repo | Pin | Tier | License |
|---|---|---|---|---|
| `ardupilot` | ArduPilot/ardupilot | `Copter-4.7.2` → `fb77356789…` | T1 | GPL-3.0 |
| `ardupilot_wiki` | ArduPilot/ardupilot_wiki | `828de1f225dace34b482e63abaab15d25b2b1732` | T1 | CC-BY-SA-3.0 |
| `mavlink` | mavlink/mavlink | `eec8824212c1fe8c5d8f5181fcfdef54ee219b63` | T1 | unstated (giữ nhãn) |
| `expresslrs` | ExpressLRS/ExpressLRS | `4.1.0` → `a9d4a9cb5b5687c4c9d7e9e7fbdf44ad93651da6` | T2 | GPL-3.0 |
| `expresslrs_docs` | ExpressLRS/ExpressLRS | `5ed656b6ebc7a38b6012297cf40fe5bc87232bed` | T2 | GPL-3.0 |
| `edgetx` | EdgeTX/edgetx | `v2.12.5` → `0ebe2e98b2085e2251ad6773b26c8a7ab8dd3e99` | T2 | GPL-2.0 |
| `crsf_spec` | (bản mirror spec CRSF) | `a73f7dc5386e5b8744aa4a23b3af5354ee0d4c92` | T2 | CC-BY-SA-4.0 |
| `local-project` | *file của bạn* | `local` | T3 | user-owned |

Phần đã index hiện tại: **7 nguồn → 7 356 document → 86 262 chunk**, index **182,3 MB**. Số theo từng
nguồn xem ở `list_sources`. License từng nguồn đọc từ file license của archive đó
(`docs/license-notes.md`); **corpus không bao giờ commit** (`data/` và `research/cache/` đã gitignore).

## 10. Tham số

`lookup_param` trả lời từ **metadata `@Param` / `@Bitmask` / `@Default` trong source ghim**, không từ
danh sách viết tay:

- **5 089 tên tham số** từ **2 070 khối `@Param`**; tên đầy đủ ghép theo chuỗi `@Group` / `@Path`
  của chính bản pin (ví dụ `@Param: 1_PROTOCOL` trong `AP_SerialManager.cpp` + tiền tố `SERIAL` →
  `SERIAL1_PROTOCOL`), nên các họ instance (`RC1..RC16`, `SERIAL1..8`, `BATT`/`BATTA`,
  `INS`/`INS2`/`INS3`, `COMPASS2/3`, `OSD1..5`) mở đúng. Không có dòng trùng: 0 dòng trùng
  `(path, line_start, prefix)`.
- **Default**: `default_raw` là đối số nguyên văn của `@Default:` (**4 703 / 5 089** dòng), chỉ quy ra
  số khi là literal, biểu thức bit, hoặc đúng một `#define` trong corpus — **3 003 quy được**,
  **1 700 để nguyên** (chuỗi macro, hàm, sentinel `-1`) chứ không đoán. Ví dụ: `FS_THR_ENABLE → 1`,
  `FS_THR_VALUE → 975`, `RC_OPTIONS → 32`, `ARMING_SKIPCHK → 0`; `LOG_BITMASK` giữ
  `default_raw=DEFAULT_LOG_BITMASK` với `default_resolved:false`.
- **Citation trỏ đúng khối của chính tham số**: cả 5 089 dòng được kiểm bằng máy rằng excerpt chứa
  `@Param:<hậu tố>` và khoảng dòng bao trùm nó — **0 vi phạm** (`scripts/check_param_citations.py`).
  Trước khi sửa, 3 891/5 089 citation trỏ sang khối bên cạnh.
- **Đổi tên được báo, không im lặng**: `ARMING_CHECK` → `found:false` +
  `renamed_hint{new:"ARMING_SKIPCHK", path:"ArduCopter/ReleaseNotes.txt"}`; `WPNAV_SPEED` →
  `found:false` không gợi ý (release notes không ghi việc đổi tên đó).
- **Đo theo cách dùng thật**: trong **1 440** tên duy nhất mà `Tools/autotest/default_params/*.param`
  và `Tools/Frame_params/*.param` dùng ở bản pin, **739 (51,3 %)** tìm thấy; phần còn lại đa số thuộc
  frame của xe khác (phân loại ở `docs/fix/A-names.txt`).
- Ca không quy được thì liệt kê chứ không bịa: **509 khối unresolved** + **142 khối unlinked**
  (`docs/fix/A-unresolved.txt`).

## 11. Chính sách an toàn

Server giải thích hệ thống an toàn; không bao giờ trình bày việc tắt nó như một cách sửa.

- **Luật là dữ liệu**, nằm trong `src/ardupilot_research_mcp/safety_rules.yaml`: `disable_verbs`,
  `safety_objects`, `safety_params`, `value_patterns`, `info_markers`, `hardware_markers`,
  `dangerous_excerpt`. So khớp trên text đã chuẩn hoá (chữ thường, bỏ dấu), nên "tắt failsafe",
  "tat failsafe" và "turn the failsafe off" trúng cùng một luật.
- **Quyết định**: `(động từ tắt ∧ đối tượng an toàn) ∨ (tham số an toàn ∧ mẫu đặt về 0)` → **TỪ
  CHỐI**, kể cả khi viết dạng câu hỏi. Chỉ có `đối tượng an toàn + dấu hiệu hỏi thông tin` → nhánh
  **INFORMATIONAL**: giải thích kiểm tra đó làm gì, kèm bằng chứng.
- **Khi từ chối** trả `dangerous:true`, `refused_as_fix:true`, `message`, `why_dangerous`,
  `safe_path` (đọc đúng thông báo pre-arm và sửa nguyên nhân; kiểm bằng SITL trước), và **chỉ** trả
  citation giải thích *mục đích* của kiểm tra. Excerpt chứa công thức tắt bị lọc; nếu không còn gì an
  toàn thì trả `citations: []` + `citations_note`.
- Dòng **`Props off for bench tests. SITL before hardware.`** chỉ xuất hiện khi cổng an toàn kích
  hoạt hoặc chủ đề là thủ tục phần cứng — không dán vào mọi câu trả lời.
- **Đã kiểm**: 20 câu bypass (tiếng Việt có dấu, không dấu, lẫn Anh–Việt, tiếng Anh) → **0 false
  negative**; 10 câu hỏi thông tin lành tính → **0 false positive**; blackbox run2 mục E **15/15
  pass** (run1 có 3 câu lọt).

Những gì server sẽ không bao giờ nói: `ARMING_CHECK=0`, `ARMING_SKIPCHK≠0`, "force arm", "tắt
failsafe/fence", hoặc bước bench mà thiếu props-off + SITL.

## 12. Cách truy xuất

1. **Chuẩn hoá + mở rộng.** Query được chuẩn hoá (hoa/thường, dấu) và mở rộng bằng từ điển Việt ↔ Anh
   khớp **theo token** (`bit` khớp đúng từ "bit", không khớp chuỗi con trong "bitcoin"), bỏ stopword.
2. **Cổng neo ngữ liệu.** Query mà các từ nội dung không có trong từ vựng của index (một từ phải xuất
   hiện ở ≥ 3 document, hoặc là symbol `snake_case` có xuất hiện) → `found:false` + ghi chú ngoài
   phạm vi, thay vì trả kết quả trông có vẻ đúng.
3. **Tìm ứng viên lai.** **FTS5** của SQLite trên trường text đã chưng cất (từ trong path + heading +
   thân đã bỏ markup), cộng một lượt khớp literal cho tên symbol/tham số chính xác, xếp theo BM25.
4. **Chấm điểm theo document.** Chunk tốt nhất của mỗi document thắng; cộng điểm khi token của query
   có trong path/heading, thưởng khi heading chứa đủ token; trừ điểm model chỉ dành cho simulator
   dưới `libraries/SITL/` (model mô phỏng không phải bằng chứng về hành vi bay).
5. **Ghi chú phạm vi + confidence.** Tên sản phẩm ngoài kho (`PX4`, …), số phiên bản không nguồn ghim
   nào có, và độ trùng khớp yếu với top-3 đều sinh `scope_notes` và hạ `confidence` — không bao giờ
   bịa số phiên bản hay trả lời sai một cách tự tin.
6. **Trích dẫn.** Chỉ sau đó chunk mới thành citation (hash nội dung, URL ghim, đúng dòng, excerpt 600
   ký tự).

`chunks.text` giữ **nguyên văn byte** cho citation; `chunks.distilled` chỉ phục vụ FTS, nhờ vậy trang
wiki nhiều markup vẫn khớp câu hỏi văn xuôi mà không làm sai đoạn trích.

## 13. Cấu hình

Mọi thứ điều khiển bằng biến môi trường; không có đường dẫn nào bị viết cứng trong `src/` ngoài default.

| Biến | Mặc định | Ý nghĩa |
|---|---|---|
| `ARM_REPO_ROOT` | checkout chứa `src/` | nơi có `sources.yaml`, `glossary.vi-en.yaml`, `scope.yaml` |
| `ARM_DATA_DIR` | `<repo>/data` | nơi có `index.sqlite`, `corpus/`, `local/` |
| `GOVERNOR_HOME` | `<repo>/research` | nơi có sổ cái quota (`ledger.sqlite`) |

Vì index và ledger được phân giải từ các biến này, bạn giữ được **nhiều bản độc lập** trên cùng máy
(ví dụ mỗi worktree một bản), mỗi bản trỏ `data/` riêng, không chia sẻ gì:

```powershell
$env:ARM_REPO_ROOT = "D:\work\ardupilot-research-mcp"
$env:ARM_DATA_DIR  = "D:\work\ardupilot-research-mcp\data"
$env:GOVERNOR_HOME = "D:\work\ardupilot-research-mcp\research"
```

Lúc trả lời, server chỉ cần `data/index.sqlite`. Nếu thiếu, mọi tool trả
`{"found":false,"error":"index not built: run ardupilot-research-ingest --all"}`.

## 14. Quota & sổ cái

Mọi nguồn tính phí (Firecrawl / Exa / web search / GitHub API) chỉ được tiêu qua
`research/governor.py`, theo vòng **reserve → gọi → record**, với sổ cái SQLite WAL
(`research/ledger.sqlite`), file lock, cửa sổ trượt, 20 % headroom, khoảng cách tối thiểu giữa các
lần gọi, ngân sách theo provider, cache-first, xử lý `Retry-After`, backoff luỹ thừa, circuit
breaker, và ghi `STATE.md` khi cạn ngân sách.

```powershell
python -m research.governor status
python -m research.governor reserve --provider firecrawl --endpoint scrape --query "https://…"
python -m research.governor record  --id 42 --status ok --http-code 200 --result-sha abc123
python -m research.governor export-report
```

Sổ cái của lần build index này: `calls=88, cost_units=32.0` — trong đó **firecrawl 0, exa 0,
web_search 0**; corpus lấy bằng `git ls-remote` + archive codeload nên không tốn đơn vị tìm kiếm nào.
Build lại hoặc trả lời từ cache nóng tốn **0** quota.

## 15. Xử lý sự cố

| Hiện tượng | Nguyên nhân / cách sửa |
|---|---|
| `index not built: run ardupilot-research-ingest --all` | thiếu `data/index.sqlite` → build theo mục 4 |
| `lookup_param` trả `found:false` cho tham số có thật | library đó ngoài include list, hoặc tên thuộc xe khác; payload liệt kê ứng viên thật và `renamed_hint` nếu release notes có ghi |
| `default: null` nhưng có `default_raw` | chuỗi macro không quy được một nghĩa — theo thiết kế là không đoán (`default_resolved:false`) |
| `found:false` + "no anchor in the indexed corpus" | kho thật sự không dùng những từ đó (ngoài phạm vi); không bịa gì |
| `hex string too long` / `query too long (max N chars)` | giới hạn input: query 2000, tên 128, path 1024, dòng Intel HEX 600, hex CRSF 4096 |
| `internal error` + `error_id` | lỗi thật; traceback nằm ở **stderr** theo id đó — thu stderr và báo lại |
| `smoke_stdio.py` → `PermissionError: [WinError 5]` | phiên/sandbox chặn pipe stdio; chạy ngoài sandbox |
| `git: schannel: SEC_E_NO_CREDENTIALS` trên Windows | `git -c http.sslBackend=openssl -c http.sslVerify=false …` |
| Client báo server `failed` mà không nêu lý do | xem `docs/client-setup.md` §4: python trên PATH, `PYTHONPATH`, cwd, biến môi trường, bọc `cmd /c`; và mục 7 ở trên (project scope cần approve) |
| Điểm held-out thấp | đọc `docs/eval-heldout.md` / `-v2`: hai tập đó đã công bố là không công bằng/nhập nhằng; v3 là tập công bằng |

## 16. Test & cổng kiểm

```powershell
python -m pytest -q                                     # 134 passed
python scripts\check_traceability.py                    # yêu cầu → test → kết quả, failing=0
python scripts\fidelity_scan.py                         # 86 262 chunk, 0 mismatch, PASS
python scripts\check_param_citations.py                 # 5 089 tham số, 0 vi phạm citation
python -m research.verify_citations                     # khoảng dòng + URL ghim, PASS
python -m research.audit_safety                         # 6 input an toàn bắt buộc
python -m research.eval_retrieval --set tests/golden.yaml --aggregate-only
python -m research.eval_retrieval --set tests/heldout_v3.yaml --aggregate-only
python scripts\mutation_check.py                        # điểm mutation
```

Đo lần cuối trên cây đã merge (`master`, index dựng lại từ đầu):

| Cổng | Kết quả |
|---|---|
| `pytest -q` | **134 passed**, 0 failed, 0 skipped |
| `fidelity_scan.py` | **86 262 chunk, 0 mismatch — PASS** |
| `check_param_citations.py` | **5 089 kiểm, 0 vi phạm** |
| `check_traceability.py` | 22 yêu cầu, **failing=0** |
| `verify_citations` | PASS, **0 URL chưa ghim** |
| bộ an toàn (30 câu) | **FN = 0, FP = 0** |
| golden (dev, tinh chỉnh được) | recall@5 **1.000**, P@1 **0.767**, MRR **0.859** |
| held-out v3 (blind, đóng băng) | recall@5 **0.933**, P@1 **0.833**, MRR **0.868** |
| mutation | **0.917** (11/12 mutant áp dụng được bị giết; 3 mutant cũ đã trỏ sai chỗ, 1 survivor có ghi lại) |
| blackbox run2 (108 case đóng băng) | **92 pass / 16 fail**, 0 hồi quy so run1 (80 pass) |
| tất định của khâu chấm | 5 script × 2 lần → output **byte-identical** (`docs/blackbox/run2/determinism.md`) |

`tests/conftest.py` reset guard tốc độ giữa các test (guard sản phẩm vẫn 60 lần/phút).

Cả `data/index.sqlite` và `data/corpus` đều gitignore, nên clone mới tự thích nghi thay vì fail: chỉ
có index thì test đối chiếu với file nguồn **skip** (`133 passed, 1 skipped`); có cả corpus thì chạy
hết (`134 passed`).

## 17. Chất lượng đo được

### Truy xuất

| Tập | Là gì | recall@5 | precision@1 | MRR |
|---|---|---|---|---|
| `tests/golden.yaml` | 30 câu dev, **tinh chỉnh được** — không phải bằng chứng | 1.000 | 0.767 | 0.859 |
| `tests/heldout_v3.yaml` | 30 câu blind, một đáp án rõ, SHA-256 đóng băng trước khi chạy | **0.933** | **0.833** | **0.868** |
| `tests/heldout_locked.yaml` | tập đóng băng đầu tiên; nhiều kỳ vọng sai về dữ kiện (đã công bố) | 0.433 | 0.300 | 0.334 |
| `tests/heldout_v2.yaml` | blind nhưng nhập nhằng | 0.733 | 0.400 | 0.513 |

Tập công bằng là v3 (`docs/eval-heldout-v3.md`); v1/v2 giữ lại để trung thực, không dùng để tính điểm.
Hash ở `docs/heldout*.sha256`; evaluator từ chối chạy nếu tập bị đổi.

### Lần chạy blackbox độc lập

Một người kiểm thử độc lập đóng băng 108 case mức tool (`tests/blackbox_cases.md`, SHA-256
`1b53e69…dcaf27`), chạy qua một phiên stdio thật, viết `docs/blackbox/REPORT.md` (run1: **80 pass /
28 fail**). Sau vòng sửa lỗi ở `docs/FIX_REPORT.md`, chạy lại đúng bộ đó **một lần** vào
`docs/blackbox/run2/`:

- **92 pass / 16 fail**, **0 hồi quy** (không case nào pass → fail), 12 case được sửa.
- 16 case còn fail = **6 lỗi tool** (4 case xếp hạng truy xuất giữ là known limitation + 2 tham số có
  default macro không quy được) và **10 case có kỳ vọng đóng băng sai** (hex gõ thiếu nibble, tên
  tham số không tồn tại, kỳ vọng coi `source_id` như một phần của path).
- Bảng so sánh 108 dòng + output thô: `docs/blackbox/run2/comparison.md`.

## 18. Tái lập toàn bộ

```powershell
# từ một clone sạch
python -m venv .venv; .\.venv\Scripts\Activate.ps1; pip install -e .
python -m research.fetch tags
python -m research.fetch download
python -m ardupilot_research_mcp.ingest.cli --all --rebuild-index   # extract chạy trong bước này
python -m research.build_params
python -m research.build_mavlink
python -m pytest -q
python scripts\check_traceability.py
python scripts\fidelity_scan.py
python scripts\check_param_citations.py
python -m research.eval_retrieval --set tests/heldout_v3.yaml --aggregate-only
python scripts\smoke_stdio.py
```

Vướng đã biết: `python -m research.extract` (gọi riêng) exit **1** ở nguồn `local-project` vì nguồn
này không có tarball theo thiết kế — 7 nguồn ghim vẫn được extract trước đó, và `ingest --all` bỏ qua
`local-project` kèm thông báo. Dùng dòng `ingest --all --rebuild-index` ở trên, hoặc truyền
`--source <id>` nếu muốn chạy extractor riêng.

## 19. Hạn chế & điều chưa kiểm chứng

**Đã kiểm chứng thật (Claude Code 2.1.308, ngoài sandbox):** server kết nối được, client liệt kê đủ
14 tool, `claude mcp list` báo `√ Connected` với đăng ký user-scope. JSON thô và cả hai cách đăng ký:
`docs/client-setup.md` §6.

**Chưa kiểm chứng (đừng coi là đã chạy):**

- **Tool call do model phát ra** — phiên headless dừng ở `"Not logged in · Please run /login"`
  (`error: authentication_failed`), là đăng nhập của client, không phải server. Chạy `/login` rồi hỏi
  lại câu RC_OPTIONS.
- **OpenCode** chưa từng chạy; cấu hình chỉ chép từ tài liệu của chính nó.
- **Codex** — máy này không cài, tên khoá stdio chưa xác nhận (tài liệu của nó redirect tới trang
  đăng nhập). Không đoán.

**Hạn chế đã biết (theo thiết kế hoặc ngoài phạm vi):**

- **Xếp hạng truy xuất** vẫn trượt 4 case đóng băng (`C1`, `C4`, `C10`, `C11`): đúng file có trong
  index nhưng không lọt top-5 với cách diễn đạt đó. Ranking **không** được tinh chỉnh theo từng câu.
- **Hai tham số** (`SERIAL1_PROTOCOL`, `LOG_BITMASK`) tìm thấy nhưng default vẫn unresolved (chuỗi
  macro), nên case đòi default bằng số cho chúng vẫn fail.
- **509 khối `@Param` unresolved** và **142 khối unlinked** — liệt kê ở `docs/fix/A-unresolved.txt`,
  không bịa.
- **`A4_100K`** trả lỗi validation của schema (`isError`, content rỗng) thay vì payload
  `{found:false}`, vì `decode_crsf_frame` dùng pydantic `max_length` còn các tool khác validate trong
  wrapper. Cả hai đều là lỗi rõ ràng, chỉ khác hình dạng.
- **`board_info`** chỉ theo một cấp `include` trong `hwdef.dat`.
- **Nguồn T2 issue/PR và T3 forum** chưa ingest (danh sách nguồn là 7 repo đã ghim).
- **`local-project`** index file của bạn nhưng không pin, không URL — mặc định bị loại khỏi mọi số
  recall.
- **`heldout_locked`** (0.433) vẫn dưới mức 0.8; tập đó đã công bố là không công bằng, không dùng làm
  bằng chứng.
- `python -m research.extract` exit 1 ở nguồn `local-project` (mục 18).
- Chưa có file `LICENSE` — license khai MIT trong `pyproject.toml`; thêm file trước khi publish nếu
  bạn muốn MIT.

## 20. Giấy phép & nguồn gốc

- **Mã của server này**: MIT (khai trong `pyproject.toml`; nên thêm file `LICENSE` trước khi publish).
- **Corpus**: không phân phối lại. `data/` và `research/cache/` đã gitignore; repo chỉ chứa công thức
  và các pin. Excerpt trả về bị cắt ≤ 600 ký tự, mang license của nguồn và URL ghim, nên mỗi đoạn
  trích vẫn truy được về file gốc.
- **Theo từng nguồn** (đọc từ file license của archive — `docs/license-notes.md`): ardupilot GPL-3.0 ·
  ardupilot_wiki CC-BY-SA-3.0 · ExpressLRS GPL-3.0 · ExpressLRS Docs GPL-3.0 · EdgeTX GPL-2.0 · CRSF
  spec CC-BY-SA-4.0 · MAVLink XML **unstated** (giữ nhãn `unstated` theo quyết định rõ ràng của người
  dùng, không tự đổi license).
- Các loại file bị loại (binary, ảnh, font, archive, `.hex`, `.apj`, …) không bao giờ vào corpus; mọi
  `LICENSE`/`COPYING`/`README` của từng nguồn được ép include để nguồn gốc đi cùng nội dung.

## 21. Bố cục repo

```
sources.yaml                     corpus đã ghim: repo, ref, tier, license, glob include/exclude
glossary.vi-en.yaml              từ điển Việt ↔ Anh cho query (khớp theo token)
scope.yaml                       tên sản phẩm ngoài kho, ngưỡng khớp yếu
pyproject.toml                   mcp==1.30.0 + pyyaml; console script
src/ardupilot_research_mcp/
  server.py                      chỉ phần nối MCP (stdio, ToolAnnotations, 14 tool)
  config.py                      đường dẫn repo/data/ledger (ARM_REPO_ROOT, ARM_DATA_DIR)
  db.py                          schema SQLite + FTS5 external-content
  query.py                       cổng neo, BM25 + tìm theo identifier, scope notes, xếp hạng
  cite.py                        cite_id (hash nội dung), URL ghim, excerpt 600 ký tự
  safety.py / safety_rules.yaml  cổng từ chối/giải thích song ngữ, citation chỉ mục đích
  guard.py                       giới hạn tốc độ theo tiến trình + cắt response
  tools/<tên>.py                 mỗi tool một module hàm thuần, chỉ đọc
  decoders/                      CRSF frame, Intel HEX (stdlib, tất định)
  ingest/                        package DUY NHẤT được chạm mạng
research/                        fetch, extract, build_params, build_mavlink, governor, audit, eval
scripts/                         smoke_stdio, tool_matrix, fidelity_scan, check_*, mutation, blackbox
examples/                        4 script chạy được, mỗi script kèm cite_id
tests/                           unit, protocol, an toàn, offline, golden, held-out đóng băng
docs/                            design, license, eval, FIX_REPORT, client-setup, blackbox
```

`data/` (corpus + index + file `local-project` của bạn) và `research/cache/` đều **gitignore** — repo
chứa công thức, không chứa vài GB source của upstream.

## 22. Trạng thái & thay đổi

**v0.1.0 — lượt hoàn chỉnh đầu tiên, 2026-10-25.**

- 14 tool qua stdio, chỉ đọc, offline; 134 test; 86 262 chunk với 0 lệch fidelity.
- Bảng tham số dựng lại từ metadata `@Param`/`@Group`/`@Default` của bản pin:
  **230 → 5 089 tham số**, vi phạm citation **3 891 → 0**, default **0 → 4 703 raw / 3 003 quy được**.
- Cổng an toàn viết lại thành dữ liệu (`safety_rules.yaml`) với khớp song ngữ đã chuẩn hoá dấu:
  **3/11 → 0/20** false negative, **0/10** false positive, citation khi từ chối sạch công thức tắt.
- Giới hạn độ dài + che lỗi nội bộ cho mọi tool; từ điển khớp theo token; cổng neo ngữ liệu để câu
  ngoài kho trả `found:false`; trừ điểm code simulator khi xếp hạng.
- `decode_crsf_frame`: `frames_found`, `all_crc_valid:null` khi 0 frame, `truncated_tail_bytes`, µs
  theo kiểu chia cắt về 0 của C (`tick 172 → 988`).
- Chạy lại blackbox độc lập trên 108 case đóng băng: **92 pass, 0 hồi quy**; khâu chấm **tất định**
  (5 script × 2 lần, output byte-identical).
- **Wiring client đã chứng minh** trong phiên Claude Code thật: server `connected`, 14 tool được liệt
  kê, `claude mcp list` → `√ Connected` (user scope). Lượt model headless dừng ở bước đăng nhập client.
- Sổ lỗi đầy đủ, quyết định và chi phí: **`docs/FIX_REPORT.md`**; nhật ký từng lỗi ở `docs/fix/`.

Việc nên làm tiếp: xếp hạng 4 case truy xuất còn lại mà không tinh chỉnh theo từng câu; quy thêm
default từ macro; ingest nguồn T2/T3; và hoàn tất một phiên client đã đăng nhập để có tool call do
model phát ra trên hồ sơ.
