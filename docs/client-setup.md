# Đăng ký MCP server `ardupilot-research` vào client (Windows)

Tài liệu này chứa **lệnh PowerShell để bạn tự chạy**, và ghi rõ phần nào đã đo trong sandbox của tôi,
phần nào **chưa kiểm (UNVERIFIED)**. Chẩn đoán đầy đủ: `docs/fix/E.md`.

Không có handshake thật từ client nào được dán trong tài liệu này. Không chỗ nào ở đây nói lỗi 8 "đã sửa".

## 0. Trạng thái kiểm chứng

| Việc | Trạng thái | Ghi chú |
|------|-----------|---------|
| `python` trên PATH đúng bản có `mcp` 1.30.0 | ĐÃ ĐO | `docs/fix/E.md` §3a |
| `python -m ardupilot_research_mcp.server` import được, 14 tool đăng ký | ĐÃ ĐO (in-process) | §3a |
| Package đã cài bằng `pip` | **KHÔNG** — chỉ chạy được nhờ `PYTHONPATH` | §3b |
| `pip install -e .` | UNVERIFIED (sandbox không mạng, thiếu `hatchling`) | §3b |
| `.mcp.json` project-scope đọc được bởi `claude` | ĐÃ ĐO (`claude mcp get`, `claude mcp list`) | §6a |
| Claude Code spawn + handshake | UNVERIFIED — sandbox chặn tạo pipe | §4a, §6b |
| OpenCode | UNVERIFIED — binary không chạy nổi trong sandbox (`EPERM` ghi `~/.local/share/opencode/log`) | §3 |
| Codex | NOT RUN — không có trên máy (`where.exe codex` exit 1) | §3 |

## 1. Ba sự thật đã đo, ảnh hưởng trực tiếp tới config

1. **`python` phải là đường dẫn tuyệt đối.** PATH trên máy có hai `python`:
   `...\Programs\Python\Python311\python.exe` (thật, có `mcp`) và
   `...\Microsoft\WindowsApps\python.exe` (**stub 0 byte**, chạy thì im lặng, exit 0). Nếu client phân giải
   `python` vào stub, tiến trình con "chạy xong" mà không nói gì → client báo `failed` không lý do.
2. **`PYTHONPATH` là bắt buộc** vì package chưa được cài (`pip show ardupilot-research-mcp` → not found;
   import không có PYTHONPATH → `ModuleNotFoundError`). Không có `PYTHONPATH` trong `env` thì server chết
   ngay khi spawn, exit ≠ 0.
3. **`ARM_DATA_DIR`/`ARM_REPO_ROOT` không bắt buộc**, nhưng nên set: index được suy từ vị trí module
   (`config.py:12-22`), **không** phụ thuộc cwd. Không set thì server dùng `data/index.sqlite` của cây
   chứa `src/` mà `PYTHONPATH` trỏ tới — tiện, nhưng dễ đọc nhầm index (worktree vs bản gốc).

File mẫu: `.mcp.json.example` (thay `<YOU>` và các `D:\path\to\...`). **Không cần `cmd /c`** — `command` là
`.exe` thật; `cmd /c` chỉ cần nếu trỏ vào shim `.cmd`/`.ps1` (bằng chứng: `docs/fix/E.md` §3e).

## 2. Claude Code — các bước chạy trên máy bạn (PowerShell)

Chạy trong thư mục repo (hoặc worktree) mà bạn muốn dùng làm `ARM_REPO_ROOT`.

```powershell
# 2.1 Lấy đường dẫn tuyệt đối của python có mcp (dùng cho mọi bước sau)
$PY = (Get-Command python).Source
$PY
& $PY -c "import mcp; print('mcp', mcp.__version__)"

# 2.2 Đăng ký (project scope, ghi vào .mcp.json)
$REPO = (Get-Location).Path
$PY = (Get-Command python).Source
claude mcp add ardupilot-research --scope project `
  -e "PYTHONPATH=$REPO\src" `
  -e "ARM_DATA_DIR=$REPO\data" `
  -e "ARM_REPO_ROOT=$REPO" `
  -- "$PY" -m ardupilot_research_mcp.server

# 2.3 Xem lại đăng ký (không spawn server)
#     (cú pháp 2.2 đối chiếu với `claude mcp add --help` của 2.1.308 — xem khối ngay dưới)
claude mcp get ardupilot-research

# 2.4 Health-check (spawn server)
claude mcp list
```

Cú pháp đã đối chiếu (`claude mcp add --help`, bản 2.1.308):

```
Usage: claude mcp add [options] <name> <commandOrUrl> [args...]
  -e, --env <env...>           Set environment variables (e.g. -e KEY=value)
  -s, --scope <scope>          Configuration scope (local, user, or project)
  -t, --transport <transport>  Transport type (stdio, sse, http). Defaults to stdio if not specified.
```

Kết quả **đã đo** ở bước 2.3 và 2.4 trong sandbox (chưa approve, nên chưa spawn):
```
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

Checking MCP server health…
ardupilot-research: python -m ardupilot_research_mcp.server - ⏸ Pending approval (run `claude` to approve)
```

Lưu ý: `command` in ra là `python` (chuỗi trần) nếu bạn đăng ký bằng `python`. Muốn loại hẳn rủi ro stub
0 byte ở §1.1 thì đăng ký bằng `$PY` như 2.2 (khi đó dòng `Command:` sẽ là đường dẫn tuyệt đối).

```powershell
# 2.5 Approve: mở claude tương tác rồi dùng /mcp để approve server project-scope.
#     Bước này UNVERIFIED trong phiên của tôi (phiên không tương tác được).
claude

# 2.6 Sau khi approve, health-check lại; kỳ vọng thấy "connected" (UNVERIFIED):
claude mcp list
```

```powershell
# 2.7 Hỏi thử một câu buộc client gọi lookup_param
claude -p "Dùng tool lookup_param tra RC_OPTIONS trong ArduCopter, chỉ in found và cite_id đầu tiên"
```

Kết quả **đúng** trông như sau — đây là payload thật của chính hàm `lookup_param` (tôi gọi in-process,
`docs/fix/E.md` §3a; **không** phải qua client):

```json
{"found": true, "query": "RC_OPTIONS", "vehicle": "ArduCopter", "version_filter": null,
 "resolved_by": "suffix",
 "params": [{"citation": {"cite_id": "ardupilot#11fb2497e2a89d95", "source_id": "ardupilot",
   "ref": "Copter-4.7.2", "path": "libraries/RC_Channel/RC_Channels_VarInfo.h",
   "lines": [84, 117], "url": "https://github.com/ArduPilot/ardupilot/blob/Copter-4.7.2/...
   RC_Channels_VarInfo.h#L84-L117"}, ...}]}
```

Dấu hiệu **sai** cần phân biệt:

- `mcp_servers:[{"name":"ardupilot-research","status":"failed"}]` ở dòng `subtype:"init"` của
  `--output-format stream-json`: server **không** khởi động (xem §4 để lấy lý do).
- `"apiKeySource":"none"` + `"Not logged in · Please run /login"`: **lỗi độc lập**, không liên quan server;
  client không chạy được lượt model nào nên không có tool call nào.

Nếu muốn tách hai lỗi này mà không cần approve, dùng cờ dynamic-config (đây là cách đã tái lập lỗi 8):

```powershell
claude -p "hi" --mcp-config .mcp.json --strict-mcp-config --output-format stream-json --verbose
```

## 3. OpenCode và Codex

- **OpenCode**: chỉ xác nhận được file `C:\Users\ADMIN\AppData\Roaming\npm\opencode.ps1` tồn tại. Chạy
  `opencode --version` trong sandbox của tôi **thất bại** trước khi làm gì:

  ```
  PlatformError: Unknown: FileSystem.open (C:\Users\ADMIN\.local\share\opencode\log\opencode.log)
  [cause]: Error: EPERM: operation not permitted, open 'C:\Users\ADMIN\.local\share\opencode\log\opencode.log'
  exit=1
  ```

  → **Cách đăng ký MCP cho OpenCode: UNVERIFIED.** Tôi không dán cú pháp config ở đây vì chưa kiểm được.
  Việc cần làm trên máy bạn: `opencode --version`, rồi xem help/doc MCP của chính bản đó; các giá trị cần
  điền vẫn là bộ đã đo ở §1 (`command` = đường dẫn tuyệt đối `python.exe`, `PYTHONPATH=<repo>\src`,
  `ARM_DATA_DIR`, `ARM_REPO_ROOT`) và chạy trong terminal **không** bị sandbox.
- **Codex**: **NOT RUN** — `where.exe codex` trả `INFO: Could not find files for the given pattern(s)` (exit 1).
  Không có gì để kiểm. Cũng chưa kiểm được phần đăng ký MCP của Codex: **UNVERIFIED**.

## 4. Vì sao lần chạy trong sandbox báo `failed` và cách lấy lý do thật

Trong sandbox `workspace-write` của phiên này, **không client stdio nào spawn được tiến trình con**:
`CreateFile` trên pipe bị từ chối.

```
PermissionError: [WinError 5] Access is denied
  File "...\asyncio\windows_utils.py", line 63, in pipe
    h2 = _winapi.CreateFile(
```

Kiểm chứng độc lập: một probe server tầm thường (`cmd /c echo`) cũng bị client báo `failed` và **không có
tiến trình con nào chạy** (`docs/fix/E.md` §4c). Vì vậy `failed` trong sandbox **không** phải do python /
`PYTHONPATH` / cwd / env / `cmd /c`.

Để lấy lý do thật, chạy trong terminal **không** bị sandbox (không confinement, không hạn chế pipe):

```powershell
cd <repo>
claude -p "hi" --mcp-config .mcp.json --strict-mcp-config --output-format stream-json --verbose 2>&1 |
  Select-Object -First 1
# Kỳ vọng: "mcp_servers":[{"name":"ardupilot-research","status":"connected",...}]
# Nếu vẫn "failed": chạy server bằng tay để xem stderr thật:
$env:PYTHONPATH="$((Get-Location).Path)\src"
$env:ARM_DATA_DIR="$((Get-Location).Path)\data"
$env:ARM_REPO_ROOT=(Get-Location).Path
& (Get-Command python).Source -m ardupilot_research_mcp.server
# MCP stdio: chờ stdin. Gõ một dòng JSON rồi Ctrl+Z Enter để đóng, hoặc Ctrl+C.
```

## 5. Nếu bạn muốn server đọc index của worktree

`.mcp.json` đang tracked trỏ `PYTHONPATH`/`ARM_DATA_DIR`/`ARM_REPO_ROOT` về
`D:\Skill_tulan\ardupilot-research-mcp` (bản gốc). Đường dẫn index **không** phụ thuộc cwd
(`docs/fix/E.md` §3c), nên chạy từ worktree vẫn dùng index bản gốc. Muốn dùng index riêng của worktree thì
đăng ký lại (2.2) từ trong worktree, hoặc sửa ba giá trị `env` trong `.mcp.json`. Tôi **không** sửa file
`.mcp.json` tracked đó (ngoài phạm vi nhánh `fix/E`).
