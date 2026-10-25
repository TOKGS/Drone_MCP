# E — lỗi 8: tại sao client báo server `failed` (CHỈ CHẨN ĐOÁN)

- Nhánh: `fix/E`, worktree `D:\Skill_tulan\wt-E`.
- Ngày: 2026-10-25. Môi trường: DSH sandbox `workspace-write`, không mạng, Python 3.11.9, `mcp` 1.30.0.
- Phạm vi: **không sửa `src/`, không sửa `tests/`**. Sản phẩm của nhánh: `docs/fix/E.md`, `docs/client-setup.md`, `.mcp.json.example`.
- Không có chỗ nào trong tài liệu này được gọi là "đã sửa". Không có handshake thật từ client trong phiên này → xem §6.

## 0. Bằng chứng gốc của lỗi 8 (đọc lại, không chạy lại)

`docs/blackbox/h/claude_stream.jsonl:1` (dòng init, trích nguyên văn phần liên quan):

```
{"type":"system","subtype":"init","cwd":"D:\\Skill_tulan\\ardupilot-research-mcp", ... "mcp_servers":[{"name":"ardupilot-research","status":"failed","source":"dynamic"}], ... "apiKeySource":"none","claude_code_version":"2.1.308", ...}
```

`docs/blackbox/REPORT.md` §5.1 (trích):

```
(b) ngay dòng init, client báo "mcp_servers":[{"name":"ardupilot-research","status":"failed"}]
    (docs/blackbox/h/claude_stream.jsonl:1) mà **không nêu lý do** → nguyên nhân khởi động thất bại
    ghi KHÔNG XÁC ĐỊNH
```

`docs/blackbox/attempt1_failure_traceback.txt` (lần chạy đầu, cùng máy):

```
  File "...\mcp\client\stdio\__init__.py", line 249, in _create_platform_compatible_process
    process = await create_windows_process(command, args, env, errlog, cwd)
  File "...\mcp\os\win32\utilities.py", line 184, in create_windows_process
    process = await anyio.open_process(
  File "...\anyio\_backends\_asyncio.py", line 2588, in open_process
    process = await asyncio.create_subprocess_exec(
  File "...\Lib\asyncio\windows_utils.py", line 63, in pipe
    h2 = _winapi.CreateFile(
PermissionError: [WinError 5] Access is denied
```

## 1. `.mcp.json` trên đĩa (tracked, 421 byte) — chép nguyên văn

```
{
  "mcpServers": {
    "ardupilot-research": {
      "type": "stdio",
      "command": "python",
      "args": [
        "-m",
        "ardupilot_research_mcp.server"
      ],
      "env": {
        "PYTHONPATH": "D:\\Skill_tulan\\ardupilot-research-mcp\\src",
        "ARM_DATA_DIR": "D:\\Skill_tulan\\ardupilot-research-mcp\\data",
        "ARM_REPO_ROOT": "D:\\Skill_tulan\\ardupilot-research-mcp"
      }
    }
  }
}
```

Kiểm tra kích thước + tracked:

```
$ Get-Content .mcp.json -Raw; (Get-Item .mcp.json).Length; git ls-files .mcp.json
421
.mcp.json
```

Ẩn khóa/token: **không có**. Ba giá trị trong `env` là đường dẫn tuyệt đối, không phải credential.
(`apiKeySource: "none"` ở §0 là trạng thái của client, không phải giá trị trong file này.)

Ghi nhận (không sửa — file này tracked và ngoài phạm vi được phép sửa): mọi đường dẫn trỏ về
`D:\Skill_tulan\ardupilot-research-mcp`, tức bản gốc, không phải worktree. Hệ quả dữ liệu: xem §3c.

## 2. Chạy chính lệnh đã đăng ký trong shell thường (stdin không phải pipe)

Lệnh đã đăng ký = `python -m ardupilot_research_mcp.server`. Chạy trực tiếp, stdin kế thừa từ shell
không tương tác (không có tty, không pipe):

```
$ Start-Process python -ArgumentList '-m','ardupilot_research_mcp.server' -RedirectStandardOutput/Err ...
HasExited=True ExitCode=
--- stdout bytes=0 ---
--- stderr bytes=0 ---
```

Exit code lấy lại qua `cmd /c ... < NUL` để đọc được `%ERRORLEVEL%`:

```
$ cmd /c "python.exe -m ardupilot_research_mcp.server < NUL & echo EXITCODE=%ERRORLEVEL%"
--- cmd stdout ---
EXITCODE=0
--- cmd stderr ---
```

Đọc output trên: server **không crash khi khởi động** — nó thoát 0 với stdout/stderr rỗng, đúng hành vi
MCP stdio khi stdin đóng ngay (transport EOF → dừng). Không có Traceback, không có lỗi import.

Giới hạn của phép thử này: stdin ở đây là EOF/kế thừa console, không phải pipe sống. Muốn giữ server
sống và bắt tay thật thì phải có pipe → bị sandbox chặn, xem §4a.

## 3. Từng giả thuyết, từng lần một

### (a) `python` trên PATH của tiến trình client có đúng bản đã cài `mcp`?

```
$ where.exe python
C:\Users\ADMIN\AppData\Local\Programs\Python\Python311\python.exe
C:\Users\ADMIN\AppData\Local\Microsoft\WindowsApps\python.exe
$ python -c "import mcp,sys;print('mcp',mcp.__file__)"
mcp C:\Users\ADMIN\AppData\Local\Programs\Python\Python311\Lib\site-packages\mcp\__init__.py
```

Đường dẫn tuyệt đối tới đúng python đó, với đúng env của `.mcp.json` (PYTHONPATH trỏ bản gốc), cwd =
bản gốc:

```
$ & "C:\Users\ADMIN\AppData\Local\Programs\Python\Python311\python.exe" -c "import ardupilot_research_mcp.server as s; print('OK', s.__file__)"
OK D:\Skill_tulan\ardupilot-research-mcp\src\ardupilot_research_mcp\server.py
exit=0
```

Trong worktree (PYTHONPATH=src), đăng ký tool trong tiến trình, không cần pipe:

```
$ python -c "import asyncio, ardupilot_research_mcp.server as s; t=asyncio.run(s.mcp.list_tools()); print('tool_count=', len(t)); print([x.name for x in t])"
tool_count= 14
['search_docs','get_chunk','lookup_param','decode_bitmask','find_source','board_info','mavlink_message','troubleshoot','get_script','decode_crsf_frame','check_intelhex_line','parse_ihex_summary','list_sources','index_status']
exit=0
```

**Kết luận (a): KHÔNG phải nguyên nhân.** `python` đầu PATH đúng là Python 3.11.9 có `mcp` 1.30.0, và
`python -m ardupilot_research_mcp.server` import được với chính env trong `.mcp.json`.

Rủi ro phụ đã đo được: `C:\Users\ADMIN\AppData\Local\Microsoft\WindowsApps\python.exe` là **stub 0 byte**
và chạy nó thì im lặng, exit 0:

```
$ & 'C:\Users\ADMIN\AppData\Local\Microsoft\WindowsApps\python.exe' -V
(no output)
exit=0
```

Nếu PATH của client (nhất là client khởi động từ GUI/desktop, không kế thừa PATH của shell này) phân giải
`python` vào stub này, tiến trình con sẽ "chạy xong ngay" mà không nói gì. Đây là **giả thuyết còn mở**,
không phải nguyên nhân của lần chạy ghi trong §0 (xem §5). Cách loại bỏ: dùng đường dẫn tuyệt đối tới
`python.exe` trong config — xem `docs/client-setup.md`.

### (b) Package có cài được không, hay chỉ chạy nhờ `PYTHONPATH=src`?

Từ cwd trung tính, **không** có PYTHONPATH:

```
$ cd C:\Windows\Temp; python -c "import ardupilot_research_mcp, sys; print('imported:', ardupilot_research_mcp.__file__)"
ModuleNotFoundError: No module named 'ardupilot_research_mcp'
exit=1
$ python -m pip show ardupilot-research-mcp
WARNING: Package(s) not found: ardupilot-research-mcp
exit=1
```

`pip install -e .` có khả thi không? `pyproject.toml` dùng `hatchling`; hatchling **không có** trong môi trường:

```
$ python -c "import hatchling, sys; print('hatchling', hatchling.__file__)"
ModuleNotFoundError: No module named 'hatchling'
exit=1
$ python -m pip install -e . --dry-run --no-deps
[still running after 120000ms; moved to background job]
```

→ treo vì pip cố lấy build backend từ mạng; đã `job_kill`. Không có mạng nên **không cài được** trong
môi trường này; kết quả thật của `pip install -e .` trên máy có mạng: **UNVERIFIED**.

**Kết luận (b): đúng một nửa, nhưng không phải nguyên nhân của lần chạy §0.** Package **không** được cài;
server chỉ chạy được nhờ `PYTHONPATH` trong `.mcp.json`. Nếu ai đó xóa/đổi biến đó thì spawn sẽ chết với
`ModuleNotFoundError` — nhưng `.mcp.json` hiện tại có set, và phép thử (a) chứng minh import OK.

### (c) cwd của server có phải đúng thư mục repo không?

`src/ardupilot_research_mcp/config.py:12-22` (đọc nguồn, không sửa):

```
def repo_root() -> Path:
    return Path(os.environ.get("ARM_REPO_ROOT") or Path(__file__).resolve().parents[2])

def data_dir() -> Path:
    override = os.environ.get("ARM_DATA_DIR")
    return Path(override) if override else repo_root() / "data"

def index_path() -> Path:
    return data_dir() / "index.sqlite"
```

Đo thật: cùng một PYTHONPATH, hai cwd khác nhau, **không** set ARM_* → cùng kết quả:

```
$ cd D:\Skill_tulan; python -c "from ardupilot_research_mcp import config as c; print('repo_root =', c.repo_root()); print('data_dir  =', c.data_dir()); print('index     =', c.index_path()); print('index_exists =', c.index_path().exists())"
repo_root = D:\Skill_tulan\wt-E
data_dir  = D:\Skill_tulan\wt-E\data
index     = D:\Skill_tulan\wt-E\data\index.sqlite
index_exists = True
exit=0
$ cd C:\Windows\Temp; python -c "from ardupilot_research_mcp import config as c; print('index =', c.index_path(), c.index_path().exists())"
index = D:\Skill_tulan\wt-E\data\index.sqlite True
exit=0
```

**Kết luận (c): KHÔNG phải nguyên nhân.** Đường dẫn index **không** phụ thuộc cwd: nó suy từ vị trí module
(`Path(__file__).resolve().parents[2]`) hoặc từ `ARM_DATA_DIR`. cwd chỉ quyết định *module nào* được import
(qua PYTHONPATH); ở đây PYTHONPATH trỏ `...\ardupilot-research-mcp\src`, nên dù cwd là worktree thì server
vẫn dùng index của **bản gốc**. Đó là vấn đề *nguồn dữ liệu*, không phải nguyên nhân `failed`.

Kiểm tra index bản gốc có tồn tại (chỉ đọc):

```
$ Get-Item D:\Skill_tulan\ardupilot-research-mcp\data\index.sqlite | Select FullName,Length
FullName : D:\Skill_tulan\ardupilot-research-mcp\data\index.sqlite
Length   : 129105920
```

### (d) Biến môi trường cần thiết

- `PYTHONPATH`: **bắt buộc** khi package chưa cài. Bằng chứng ngược ở (b): không có → `ModuleNotFoundError`.
- `ARM_DATA_DIR`, `ARM_REPO_ROOT`: **không bắt buộc**. Bằng chứng ở (c): bỏ cả hai vẫn ra đúng
  `D:\Skill_tulan\wt-E\{data,index.sqlite,sources.yaml}` nhờ fallback theo vị trí module
  (`sources = D:\Skill_tulan\wt-E\sources.yaml True`).
- Không có biến nào khác được đọc lúc khởi động: `grep -rn "ARM_DATA_DIR|ARM_REPO_ROOT|index\.sqlite"` trên
  `src/` chỉ ra `config.py:13,17,22` và `ingest/cli.py:56` (CLI ingest, không chạy trong server).

**Kết luận (d): KHÔNG phải nguyên nhân.** Không thiếu biến nào; `PYTHONPATH` đã có trong `.mcp.json`.

### (e) Trên Windows có cần bọc `cmd /c`?

Đo được:

```
$ cmd /c "python -V"
Python 3.11.9
exit=0
$ cmd /c "where python"
C:\Users\ADMIN\AppData\Local\Programs\Python\Python311\python.exe
C:\Users\ADMIN\AppData\Local\Microsoft\WindowsApps\python.exe
$ claude mcp get ardupilot-research
  Type: stdio
  Command: python
  Args: -m ardupilot_research_mcp.server
```

**Kết luận (e): không cần `cmd /c` để server chạy đúng.** Claude Code gọi `CreateProcess` trực tiếp, không
qua shell; `python` là `.exe` thật nên không cần `.cmd` shim. `cmd /c` chỉ là cách chữa chấp nhận được nếu
`command` trỏ vào một shim `.cmd`/`.ps1` — không phải trường hợp ở đây. Bọc `cmd /c` không sửa được lỗi §0
vì tiến trình con **chưa từng được tạo** (§4).

## 4. Phát hiện quyết định: client không tạo nổi tiến trình con trong sandbox này

### 4a. Một MCP stdio client thật trong sandbox này (lead cho phép chạy)

```
$ python scripts\smoke_stdio.py
  File "...\mcp\os\win32\utilities.py", line 169, in create_windows_process
    process = await anyio.open_process(
  File "...\anyio\_backends\_asyncio.py", line 2588, in open_process
    process = await asyncio.create_subprocess_exec(
  File "...\asyncio\windows_utils.py", line 136, in __init__
    stdin_rh, stdin_wh = pipe(overlapped=(False, True), duplex=True)
  File "...\asyncio\windows_utils.py", line 63, in pipe
    h2 = _winapi.CreateFile(
PermissionError: [WinError 5] Access is denied
exit=-1
```

Đây **đúng lớp lỗi** của `docs/blackbox/attempt1_failure_traceback.txt` (§0): sandbox `workspace-write`
từ chối tạo pipe → không client nào spawn được server stdio trong sandbox này. Theo luật: phần phụ thuộc
pipe **không chẩn đoán được trong sandbox**; tôi không đoán thêm gì từ đây.

### 4b. Tái lập đúng triệu chứng `status:"failed"` của lỗi 8 trong phiên này

Chạy lại chính lệnh trong H_evidence với `.mcp.json` của worktree:

```
$ claude -p "reply with the single word ok" --mcp-config .mcp.json --strict-mcp-config --output-format stream-json --verbose
{"type":"system","subtype":"init","cwd":"D:\\Skill_tulan\\wt-E", ... "mcp_servers":[{"name":"ardupilot-research","status":"failed","source":"dynamic"}], ... "apiKeySource":"none","claude_code_version":"2.1.308", ...}
{"type":"assistant","message":{... "content":[{"type":"text","text":"Not logged in · Please run /login"}], ... "error":"authentication_failed", ...}}
{"type":"result", ... "terminal_reason":"api_error", "is_error":true, "num_turns":1, "duration_ms":376, ...}
exit=-1
```

→ Lỗi 8 **tái lập được**, y hệt §0 (cùng `status: failed`, cùng `source: dynamic`, cùng không có lý do).

### 4c. Thí nghiệm tách nguyên nhân: client có spawn được **bất kỳ** server stdio nào không?

Config thử chỉ chạy `cmd /c echo` (không liên quan tới python/ArduPilot), chạy từ workspace nên ghi được file:

```
$ type %TEMP%\arm_probe_mcp2.json
{"mcpServers":{"probe":{"type":"stdio","command":"cmd","args":["/c","echo SPAWNED> D:\\Skill_tulan\\wt-E\\.probe_spawn.txt"]}}}

$ claude -p "hi" --mcp-config %TEMP%\arm_probe_mcp2.json --strict-mcp-config --output-format stream-json --verbose
mcp_servers=[{"name":"probe","status":"failed","source":"dynamic"}]

$ if (Test-Path D:\Skill_tulan\wt-E\.probe_spawn.txt) {...} else { "PROBE FILE MISSING -> child process never ran" }
PROBE FILE MISSING -> child process never ran
```

Lặp lại lần 2 với file probe trong `%TEMP%`: cùng kết quả (`status failed`, file không có).

**Đọc output trên:** client báo `failed` cho **cả** một server tầm thường (`cmd /c echo`), và **không có
tiến trình con nào chạy**. Vậy `failed` ở đây **không phải** do `python`/`PYTHONPATH`/cwd/env/`cmd /c` của
server này — client không spawn nổi tiến trình con trong sandbox (khớp 4a: `CreateFile` trên pipe bị từ chối).

## 5. Nguyên nhân — trạng thái từng phần

| # | Điều | Trạng thái | Bằng chứng |
|---|------|-----------|-----------|
| 1 | `python` trên PATH đúng bản có `mcp` 1.30.0 | KHÔNG phải nguyên nhân | §3a |
| 2 | Package chưa cài, chỉ chạy nhờ `PYTHONPATH` | ĐÚNG là sự thật môi trường, KHÔNG phải nguyên nhân ở config hiện tại | §3b |
| 3 | cwd phải là repo | SAI (config suy từ vị trí module) | §3c |
| 4 | Thiếu biến môi trường | SAI | §3d |
| 5 | Cần `cmd /c` trên Windows | SAI | §3e |
| 6 | Client không tạo được pipe → không spawn được server nào → `status:"failed"` không kèm lý do | **Nguyên nhân của lần tái lập trong sandbox này** | §4a, §4c |
| 7 | Lần chạy ghi trong `docs/blackbox/h/claude_stream.jsonl:1` có đúng nguyên nhân 6 hay không | **UNKNOWN** — cùng sandbox, cùng lớp lỗi, nhưng client không in lý do nên không có bằng chứng trực tiếp | §0, §4b |
| 8 | Ngoài sandbox (terminal thường, không confinement) client có bắt tay được không | **UNVERIFIED** — không chạy được trong phiên này (pipe bị chặn) | §4a |
| 9 | Không có credential (`apiKeySource:"none"`) | Chặn **độc lập** thứ hai: 0 lượt model → 0 tool call, kể cả khi server sống | §4b |
| 10 | `.mcp.json` project-scope cần approve | Đo được ở client: `Status: ⏸ Pending approval (run 'claude' to approve)` | §6a |

Chốt: trong sandbox này, cái làm client báo `failed` **không kèm lý do** là **không spawn được tiến trình
con** (§4c) — nó xảy ra trước mọi thứ thuộc về server này. Còn lần chạy lịch sử chỉ có thể nói **UNKNOWN**,
vì client không in lý do; muốn biết chắc phải chạy lại ngoài sandbox (§6).

## 6. Những gì tôi KHÔNG kiểm được (và lệnh để lead tự kiểm)

Không tuyên bố đã sửa: **chưa có handshake thật từ client** nào được dán trong tài liệu này.

### 6a. Đăng ký + trạng thái (đo được, không cần pipe)

```
$ claude mcp get ardupilot-research
ardupilot-research:
  Scope: Project config (shared via .mcp.json)
  Status: ⏸ Pending approval (run `claude` to approve)
  Type: stdio
  Command: python
  Args: -m ardupilot_research_mcp.server
  Environment:
    PYTHONPATH=D:\Skill_tulan\ardupilot-research-mcp\src
    ARM_DATA_DIR=D:\Skill_tulan\ardupilot-research-mcp\data
    ARM_REPO_ROOT=D:\Skill_tulan\ardupilot-research-mcp
exit=0

$ claude mcp list
Checking MCP server health…
ardupilot-research: python -m ardupilot_research_mcp.server - ⏸ Pending approval (run `claude` to approve)
exit=0
```

Đọc: `claude mcp list` **không** spawn server khi còn "Pending approval" → muốn thấy handshake phải approve
(phiên `claude` tương tác, `/mcp`) hoặc dùng `--mcp-config ... --strict-mcp-config`.

### 6b. Handshake (UNVERIFIED trong phiên này)

Chạy trong terminal **không** bị sandbox (theo `docs/client-setup.md` §4) rồi dán nguyên văn output. Kỳ vọng
đúng trông như sau — trích từ handshake **đã ghi thật** bằng stdio ở lần blackbox (`docs/blackbox/raw/_meta/handshake.json`,
không phải từ phiên này):

```
{
  "serverInfo": {"name": "ardupilot-research", "version": "1.30.0", ...},
  "protocolVersion": "2025-11-25",
  "capabilities": {"prompts": {...}, "resources": {...}, "tools": {"listChanged": false}, ...}
}
```

(`tools_list.json` cùng lần chạy liệt kê đủ tên tool; `python -c ... list_tools()` ở §3a đếm được 14 tool.)

- Handshake qua `claude` CLI: **UNVERIFIED**.
- Handshake qua OpenCode: **UNVERIFIED** (chỉ xác nhận `C:\Users\ADMIN\AppData\Roaming\npm\opencode.ps1` tồn tại).
- Handshake qua Codex: **NOT RUN** — `where.exe codex` → `INFO: Could not find files for the given pattern(s)`, exit 1.

## 7. Đã thử gì và không lặp lại

| Thử | Kết quả | Có lặp lại? |
|-----|---------|-------------|
| `smoke_stdio.py` (client thật, pipe) | `PermissionError: [WinError 5]` | Không — sandbox chặn, luật C: dừng |
| `pip install -e . --dry-run` | treo >120 s (không mạng) | Không — đã kill |
| `claude -p --mcp-config .mcp.json --strict-mcp-config` | tái lập `status:"failed"` | Có (1 lần, để tái lập) |
| probe `cmd /c echo` | `status:"failed"`, không có file → không spawn | Có (2 lần, để chắc) |
| `claude mcp list` | Pending approval, không spawn | Không cần nữa |

## 8. Output thô bổ sung (cho `docs/client-setup.md`)

`claude mcp add --help` (2.1.308) — để viết đúng cú pháp đăng ký:

```
Usage: claude mcp add [options] <name> <commandOrUrl> [args...]
  -e, --env <env...>           Set environment variables (e.g. -e KEY=value)
  -s, --scope <scope>          Configuration scope (local, user, or project) (default: "local")
  -t, --transport <transport>  Transport type (stdio, sse, http). Defaults to stdio if not specified.
exit=0
```

`opencode --version` — không chạy nổi trong sandbox, nên phần OpenCode là UNVERIFIED:

```
opencode.exe : PlatformError: Unknown: FileSystem.open (C:\Users\ADMIN\.local\share\opencode\log\opencode.log)
+   & "$basedir/node_modules/@opencode/cli/bin/opencode.exe"   $args
    at Ol (B:/~BUN/root/chunk-qt0mynck.js:2:1151)
    at guarded (internal:shared:112:26) {
  [cause]: Error: EPERM: operation not permitted, open 'C:\Users\ADMIN\.local\share\opencode\log\opencode.log'
exit=1
```

`lookup_param` gọi in-process (không qua client) — payload "đúng trông như thế nào" cho mục kiểm thử tay:

```
$ python -c "import json; from ardupilot_research_mcp.tools.lookup_param import lookup_param; print(json.dumps(lookup_param(name_or_pattern='RC_OPTIONS'), ensure_ascii=False)[:900])"
{"found": true, "query": "RC_OPTIONS", "vehicle": "ArduCopter", "version_filter": null, "resolved_by": "suffix", "params": [{"citation": {"cite_id": "ardupilot#11fb2497e2a89d95", ... "path": "libraries/RC_Channel/RC_Channels_VarInfo.h", "lines": [84, 117], ...}}]}
exit=0
```

## 9. Trạng thái lỗi 8

**UNKNOWN** (nguyên nhân lịch sử) + **đã tái lập trong sandbox với nguyên nhân đo được là "không spawn được
tiến trình con"**. Không có handshake thật từ client → không tuyên bố sửa. Việc còn lại của lead: chạy §6b
ngoài sandbox và dán output.

