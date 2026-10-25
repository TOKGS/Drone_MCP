# H — dùng thật qua client: NOT RUN (có lý do, kèm bằng chứng thô)

## Đã làm được: đăng ký server vào một client thật

Lệnh (chạy trong `D:\Skill_tulan\ardupilot-research-mcp`):

```
claude mcp add ardupilot-research --scope project \
  -e "PYTHONPATH=D:\Skill_tulan\ardupilot-research-mcp\src" \
  -e "ARM_DATA_DIR=D:\Skill_tulan\ardupilot-research-mcp\data" \
  -e "ARM_REPO_ROOT=D:\Skill_tulan\ardupilot-research-mcp" \
  -- python -m ardupilot_research_mcp.server
```

Kết quả: `Added stdio MCP server ardupilot-research ... to project config`,
`File modified: D:\Skill_tulan\ardupilot-research-mcp\.mcp.json`.

`claude mcp get ardupilot-research` trả:

```
ardupilot-research:
  Scope: Project config (shared via .mcp.json)
  Status: ⏸ Pending approval (run `claude` to approve)
  Type: stdio
  Command: python
  Args: -m ardupilot_research_mcp.server
```

Đây là bằng chứng **đăng ký** thành công (file `.mcp.json` có trên đĩa, đúng
`command`/`args`/`env`), không phải bằng chứng handshake.

## Không làm được: handshake + 3 lần gọi tool

Lệnh thử (chạy thật, không mô phỏng):

```
claude -p "<prompt yêu cầu gọi 3 tool>" --mcp-config .mcp.json --strict-mcp-config \
  --allowedTools "mcp__ardupilot-research__decode_crsf_frame \
                  mcp__ardupilot-research__lookup_param \
                  mcp__ardupilot-research__mavlink_message" \
  --output-format stream-json --verbose
```

Kết quả: exit code 1, stdout 3 dòng, stderr rỗng. Nội dung thô ở
`docs/blackbox/h/claude_stream.jsonl`:

- **dòng 1** (`type:"system", subtype:"init"`):
  `"mcp_servers":[{"name":"ardupilot-research","status":"failed","source":"dynamic"}]`
  — client báo server khởi động **thất bại**; và `"apiKeySource":"none"`.
- **dòng 2** (`type:"assistant"`, `"error":"authentication_failed"`):
  `"Not logged in · Please run /login"`
- **dòng 3** (`type:"result"`, `"is_error":true`, `"terminal_reason":"api_error"`,
  `"num_turns":1`, `"duration_ms":335`).

Hai lý do chặn, tách biệt:

1. **Không có credential** (`apiKeySource: none`, "Not logged in"): client không chạy được
   một lượt model nào, nên không có tool call nào được phát ra. Đây là lý do quyết định —
   kể cả khi server khởi động được, cũng không có handshake + 3 tool call qua client.
2. **Server entry `status: "failed"`** ngay ở dòng init. Client **không in lý do** thất bại.
   Nguyên nhân khả dĩ là giới hạn sandbox đã gặp ở lần chạy đầu
   (`docs/blackbox/attempt1_failure_traceback.txt`: tiến trình bị confined không tạo được
   pipe, `PermissionError: [WinError 5]`), nhưng vì client không nêu lý do, phần này ghi
   **KHÔNG XÁC ĐỊNH** thay vì đoán.

## Hệ quả cho báo cáo

Mục H = **NOT RUN**: 0 case, 0 pass, 0 fail. Không được tính là "đạt".
Handshake thật và 110 case của mục A–G đã chạy qua stdio thật bằng
`scripts/blackbox_run.py` (bằng chứng: `docs/blackbox/raw/_meta/handshake.json`,
`docs/blackbox/raw/_meta/tools_list.json`), nhưng đó là client tự viết bằng mcp SDK,
không phải một client thương mại đã đăng ký — đúng như mục H yêu cầu phân biệt.
