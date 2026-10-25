# FIX_REPORT — sửa 8 lỗi blackbox của MCP `ardupilot-research`

Lead điều phối, 6 nhánh + 1 sub kiểm chứng độc lập. Mọi con số dưới đây đều có đường dẫn output thô.
Base trước khi sửa: `7fe0382` (bộ case đóng băng ở `4010ad5`, hash khớp). Trạng thái cuối: `master`.

Không có ngưỡng nào bị hạ, không test đóng băng nào bị sửa, không case nào bị chạy lại để "cho pass".

---

## (a) Trạng thái từng lỗi 1–8

| # | Lỗi | Trạng thái | Commit test-fail (đỏ thật) | Commit fix | Output thô |
|---|---|---|---|---|---|
| 1 | Citation trỏ sai khối `@Param` (5/6 entry B1) | **FIXED** | `ec61752` | `76f4b61` | `docs/fix/A-citations-before.txt` (3891 vi phạm) → `docs/fix/A-citations-after.txt` (0); `scripts/check_param_citations.py` |
| 2 | `default` luôn `null`, DB 0/230 row `default_value` | **FIXED** | `6636e69` | `31f6027` | `docs/fix/A-defaults-check.txt`; run2 `docs/blackbox/run2/B1_*.json` |
| 3 | Phủ tham số: allowlist thiếu thư mục, `SERIAL1_PROTOCOL`/`BATT_FS_LOW_ACT` không có | **FIXED** | `f1b1706` | `d3030dc` | `docs/fix/A-coverage-before.txt`, `A-names.txt`, `A-unresolved.txt` |
| 4 | Cổng an toàn: 3/11 câu bypass tiếng Việt không bị chặn, 1 case trả đúng bước tắt failsafe | **FIXED** | `7af72ba` (+ vòng 2 `8234bc0`) | `9361057` (+ vòng 2 `2f6b889`); `dc5bcc0` conftest | `docs/fix/B.md`, `tests/safety_cases_v2.yaml`, run2 `E_*.json` |
| 5 | Glossary khớp chuỗi con ("bitcoin"→"bit") + không có cờ ngoài phạm vi | **FIXED** | `bc5ef17` | `c0088c6` | `docs/fix/C.md`, `C-5-prefix.txt`, run2 `D1/D2/D4` |
| 6 | `decode_crsf_frame`: µs lệch 1, `all_crc_valid:true` khi 0 frame | **FIXED** | `fdf38e4` | `fb981a1` | `docs/fix/D.md`, run2 `A3/A4_*` |
| 7 | Thiếu `maxLength`/validate + rò lỗi SQL thô (`LIKE or GLOB pattern too complex`) | **FIXED** | `8a570e7` | `22b9fa8` | `docs/fix/C.md`, `C-7-prefix.txt`, run2 `F_MB` |
| 8 | Client báo `status: failed` không nêu lý do | **FIXED** — nguyên nhân là project-scope `.mcp.json` chưa duyệt; server chạy được trong hai client thật, và case H có tool call do model phát ra trên OpenCode | — | `ea2992f`, `511c4bb` (docs) + mục (g) | `docs/fix/E.md`, `docs/client-setup.md` §6-7, `docs/blackbox/h/opencode_stream.jsonl` |

Hồi quy do nhánh A gây ra (corpus mở rộng) được xử lý ở nhánh F, giao lại đúng chủ sở hữu `query.py`:
`bc0efc5` (test-fail) → `5857835`, `9d07c28` (test-fail) → `7b8b314`; report `docs/fix/F.md`.

Merge (thứ tự): D `e1f2f9d` → E `4d5ba12` → B `67f4e80` → C `a36790b` → A `f169cd5` → F `61b1d71`.

**Trạng thái master sau khi merge + dựng lại index từ đầu** (raw, chạy trên `data/index.sqlite` mới):

```
python -m pytest -q                        → 133 passed
python scripts/check_param_citations.py    → params checked: 5089 / citation violations: 0
python scripts/fidelity_scan.py            → TOTAL 86262 chunks, 0 mismatch, fidelity: PASS
python scripts/check_traceability.py       → requirements=22 failing=0
python -m research.eval_retrieval --set tests/golden.yaml --aggregate-only
                                           → recall@5 1.000 · precision@1 0.767 · MRR 0.859
python -m research.eval_retrieval --set tests/heldout_v3.yaml --aggregate-only
                                           → recall@5 0.933 · precision@1 0.833 · MRR 0.868
index_status                               → documents 7356 · chunks 86262 · params 5089 · 182.3 MB
```

---

## (b) So sánh run1 → run2 (108 case)

Verifier độc lập: `verify-run2`. Báo cáo đầy đủ (bảng 108 dòng + output thô):
**`docs/blackbox/run2/comparison.md`**. Run2 raw: `docs/blackbox/run2/` (commit `f1002a6`); run1
(`docs/blackbox/raw/`) không bị chạm (`git status` rỗng, diff 0).

| | pass | fail | chưa chạy |
|---|---|---|---|
| run1 (bộ gốc) | 80 | 28 | 1 (H) |
| run2 (sau 6 nhánh) | **92** | **16** | 1 (H) |

- **Hồi quy (pass → fail): KHÔNG CÓ — 0 case.** (`comparison.md` §6)
- **Cải thiện fail → pass: 12 case** — `B1_FS_THR_ENABLE`, `B1_FS_THR_VALUE`, `B1_RC_OPTIONS`,
  `B1_RC_PROTOCOLS`, `B1_ARMING_SKIPCHK`, `B1_BATT_FS_LOW_ACT`, `D1`, `D2`, `D4`, `E_BYPASS_03`,
  `E_BYPASS_08`, `E_BYPASS_11`.
- Run2: E 15/15 pass (run1: 12/15, 3 false negative), D 3/5 pass (run1: 0/5), F 12/12, G 20/20
  citation + 20/20 `get_chunk`, A 26/29, B 11/15, C 5/12.
- 16 case còn fail = **6 TOOL SAI** (`B1_SERIAL1_PROTOCOL`, `B1_LOG_BITMASK`, `C1`, `C4`, `C10`,
  `C11`) + **10 KỲ VỌNG SAI** (`A1`, `A2`, `A10_ARMING_CHECK`, `B1_ARMING_CHECK`, `B1_WPNAV_SPEED`,
  `C2`, `C3`, `C12`, `D3`, `D5`) + 0 không xác định.
- Run2 là **đúng một lần chạy**: `_meta/env.json` `started=2026-10-25T20:16:31+0700`, `summary.tsv`
  111 dòng (header + 110 case, id unique), 116 file trong cửa sổ 20:16:31–20:17:35, bản copy trong
  repo byte-identical 116/116.
- Verifier đã phải sửa **duy nhất** `verify_a.py` (bản sao `bb-run2/scripts/verify_a_run2.py`) vì
  `A4_100K` ở run2 trả lỗi schema (`isError=true`, text không phải JSON) thay vì payload; tiêu chí
  pass/fail không đổi, 4 script còn lại chạy nguyên bản.

---

## (c) Số liệu trước/sau

| Đại lượng | Trước | Sau | Cách lấy |
|---|---|---|---|
| Tham số trong bảng | 230 | **5089** | `index_status`, `db.counts()` |
| Khối `@Param` được phủ | 311 khối (allowlist cũ) | **2070 khối** (5089 tên, 0 dòng trùng `path+line+prefix`) | `docs/fix/A.md` §A-3 |
| Tên `.param` tìm thấy / tổng | — (chưa có bảng) | **739 / 1440 = 51,3 %** trên 122 file `Tools/autotest/default_params` + `Tools/Frame_params`; 701 tên còn lại đa số thuộc xe khác (phân loại: `A-names.txt`) | `docs/fix/A-names.txt` |
| Vi phạm citation `@Param` | **3891 / 5089** | **0 / 5089** | `A-citations-before.txt` → `A-citations-after.txt` |
| Có `default_raw` | 0 / 230 | **4703 / 5089** | `A-defaults-check.txt` |
| `default` quy được số | 0 | **3003** (1700 không quy được, 509 khối unresolved) | `docs/fix/A.md` §A-2 |
| Cổng an toàn — false negative | 3 / 11 (run1, `REPORT.md` §3) | **0 / 20** | `tests/safety_cases_v2.yaml`, tự đo lại trên master: `cases=30 false_negative=0 false_positive=0` |
| Cổng an toàn — false positive | 0 / 4 | **0 / 10** | như trên |
| Index | 4908 doc / 65 509 chunk / **123,1 MB** | 7356 doc / **86 262 chunk** / **182,3 MB** | `index_status`, `fidelity_scan` |
| pytest | 80 passed | **133 passed** | `python -m pytest -q` |
| golden (dev set, tinh chỉnh được) | 1.000 / 0.767 / 0.865 | 1.000 / **0.767** / 0.859 | `eval_retrieval --aggregate-only` |
| heldout v3 (blind, đóng băng) | 0.933 / 0.833 / 0.868 | **0.933 / 0.833 / 0.868** | như trên |
| heldout_locked (bộ bị "burn", kỳ vọng sai) | 0.467 / 0.267 / 0.337 | 0.433 / 0.300 / 0.334 | như trên — vẫn FAIL, đã biết là bộ không công bằng |

---

## (d) NOT FIXED / PARTIAL và known limitation

- **C1, C4, C10, C11** (4 case "TOOL SAI" về truy xuất): KHÔNG sửa ranking để cứu từng câu — brief C-5b.4
  cấm rõ. C10 nay đã index `AP_SerialManager` (3 document) nhưng vẫn không lọt top-5; C11 có 4 document
  EdgeTX có `crossfire` trong path nhưng vẫn không lọt top-5; C4 `AP_RCProtocol_CRSF.cpp` có trong index
  nhưng không lọt top-5; C1 excerpt chưa chứa `0xD5`.
- **B1_SERIAL1_PROTOCOL, B1_LOG_BITMASK**: đã `found:true` (lỗi 3 xong) nhưng `default` vẫn chưa quy được
  (`DEFAULT_SERIAL1_PROTOCOL`, `DEFAULT_LOG_BITMASK`) → giữ FAIL theo đúng tiêu chí run1 dùng cho nhóm
  `default`. Đây là "macro default không quy được", nằm trong 1700 dòng unresolved.
- **H — client thật: NOT RUN.** E chỉ chẩn đoán; handshake từ client **UNVERIFIED**. Nguyên nhân đo được
  trong sandbox: pipe stdio bị chặn (`PermissionError: [WinError 5]`), không phải python/PYTHONPATH/cwd/env/
  `cmd /c`. Lệnh để tự chạy ngoài sandbox: `docs/client-setup.md` §4.
- **Tham số có tiền tố không ghép được**: 509 khối `unresolved_blocks` + 142 `unlinked_blocks`
  (`docs/fix/A-unresolved.txt`) — không đoán tên, không đưa vào bảng.
- **`A4_100K` đổi hình dạng lỗi**: run1 trả payload `{found:false, error}`; run2 trả lỗi schema của SDK
  (`isError=true`) vì `decode_crsf_frame` dùng `Field(max_length=4096)`, trong khi 11 tool khác do nhánh C
  giới hạn bằng wrapper trả payload. Vẫn PASS theo case đóng băng (case cho phép `isError`), nhưng **không
  thống nhất giữa các tool** — ghi nhận, không sửa trong lượt này.
- **`B2`**: `index_status` nay công bố `params=5089`, trong khi báo cáo cũ ghi 214/241. 5089 tên đã ghép
  prefix không so trực tiếp được với 3368 khối `@Param` tại pin (khác đơn vị); verifier ghi cả hai.
- **T2/T3** (issues/PR, forum) vẫn chưa ingest; `board_info` vẫn chỉ theo 1 cấp `include` — như trước khi sửa.
- **`heldout_locked` 0.467 → 0.433**: bộ này đóng băng với kỳ vọng sai (đã công bố), vẫn dưới 0,8; thay đổi
  1 câu sau khi corpus mở rộng. Không dùng làm bằng chứng.
- **Tái lập**: `python -m research.extract` (lệnh trong `FINAL_REPORT.md` §How to reproduce) **exit 1** vì cố
  extract nguồn `local-project` không có tarball (`research/cache/repos/local-project.tar.gz`). 7 nguồn thật
  vẫn extract xong trước khi lỗi; chuỗi ingest → build_params → build_mavlink chạy đủ, exit 0.
- **Code coverage: NOT RUN** (không cài `coverage` trong phiên này).

---

## (e) Quyết định của lead và mọi chỗ nới luật

1. **Từ chối A sửa `query.py`** dù A xin: file thuộc nhánh C (đã merge), ưu tiên đúng chủ sở hữu →
   mở nhánh **F** giao lại cho `fix-c`. Ghi ở `docs/fix/STATE.md` mục "Quyết định của lead".
2. **Cho phép A thử** (trong write-scope của A) loại `libraries/SITL/**` để đo; kết quả P@1 về 0.767 nhưng
   case ngoài kho vẫn fail nên A đã revert — giữ làm bằng chứng, không giữ code.
3. **Cho phép tạo `tests/conftest.py`** (ngoài write-scope ban đầu của B): sau khi rebase, guard 60 lần/phút
   là trạng thái toàn cục theo tiến trình làm 1 test đỏ (`SlowDown: slow down: 35s`). Fixture chỉ xoá dấu thời
   gian giữa các test, **không** đổi `MAX_CALLS_PER_MINUTE` (guard sản phẩm nguyên vẹn).
4. **Cho B làm vòng 2** sau khi lead review `audit_safety`: citation khi REFUSE vẫn chứa câu "correct the
   problem or disable the check" / "skip a failing check" — trái brief B.5. Sau vòng 2 mỗi refusal còn đúng 1
   citation mục đích; nếu lọc hết thì trả `citations: []` + `citations_note` (không nới ngược).
5. **Merge A khi master còn 1 test đỏ** (out-of-corpus) — quyết định có chủ ý: 2 hồi quy là hệ quả của corpus
   lớn hơn, sửa ở tầng C (F), và trạng thái đỏ được ghi lại trước khi mở F; sau F master xanh (133 passed).
   Trong lúc đỏ, mọi con số đã công bố ngay tại `docs/fix/STATE.md` và commit `ac172c8`.
6. **Lead tự chạy run2 với quyền `danger-full-access`** thay vì để verifier chạy: sandbox `workspace-write`
   chặn tạo pipe (`WinError 5`) — chính là nguyên nhân lỗi 8. Lệnh chạy đúng MỘT lần trong worktree cách ly
   `D:\Skill_tulan\bb-run2` (clone bằng `git worktree`, `docs/blackbox/raw` đã bỏ trước khi chạy) để không
   ghi đè run1; verifier độc lập chỉ chấm điểm + so sánh.
7. **Không thêm** `ARDU_MCP_INDEX`/`ARDU_MCP_LEDGER`: code đã có `ARM_REPO_ROOT`/`ARM_DATA_DIR` và
   `GOVERNOR_HOME`, mỗi worktree tự trỏ index riêng — không cần sửa `src/` (đã kiểm bằng in `index_path`).
8. **Nhánh chính là `master`**, không phải `main` như FIX_SPEC ghi → rebase/merge vào `master`.
9. Lỗi encoding: commit `4c58a4c` làm hỏng `docs/fix/STATE.md` (round-trip PowerShell `Get-Content/Set-Content`
   không `-Encoding utf8`); đã phục hồi từ `58db470` và sửa ở `e52d111`. Không ảnh hưởng code.
10. Không nới ngưỡng nào: golden, heldout v3, frozen case, `tests/golden.yaml`, `tests/heldout_*.yaml` giữ
    nguyên; kiểm bằng `git status` sạch với các file đó.

---

## (f) Chi phí thực tế

Harness không công bố token/chi phí từng sub trong phiên này → **token và tiền: UNKNOWN** (không ước lượng).
Đo được: số bước/commit và ngân sách đã cấp.

| Sub | Nhánh | Ngân sách cấp | Commit trên nhánh | Ghi chú |
|---|---|---|---|---|
| `fix-a` | A | 150 bước | 6 | 1 lần rebuild index (123 → 182 MB), thử 3 guard + thử bỏ SITL rồi revert |
| `fix-b` | B | 80 bước (+ ~40 vòng 2) | 5 | 2 vòng: gate + lọc citation; 1 vòng sửa hồi quy guard |
| `fix-c` | C, F | 100 + 60 bước | 3 + 4 | C: 5+7; F: 2 hồi quy do corpus |
| `fix-d` | D | 50 bước | 2 | |
| `fix-e` | E | 40 bước | 2 | chỉ docs |
| `verify-run2` | — | 50 bước | 0 (1 file) | 1 lần chạy script sửa tối thiểu, có khai báo |

Số liệu thô khác: 110 lần gọi tool trong run2 (một phiên stdio, 0 transport error, ~64 s);
không có lần gọi Exa/Firecrawl/web_search nào trong toàn bộ quá trình sửa.

---

## (g) Bổ sung sau khi người dùng yêu cầu: kiểm chứng client thật + tính tất định

Hai khoảng trống được nêu trong báo cáo trước đã được đo lại (ngoài sandbox, Claude Code `2.1.308`,
Python 3.11.9, `mcp` 1.30.0). Không có ngưỡng nào bị đổi.

### (g.1) Client thật — server lên được, 14 tool được expose

```powershell
cd D:\Skill_tulan\client-verify
claude -p "Call the tool lookup_param (RC_OPTIONS) and tell me only the numeric default." `
  --mcp-config .\mcp.json --strict-mcp-config --output-format stream-json --verbose
```

Dòng `system/init` (nguyên văn, rút gọn phần tools):

```
"mcp_servers":[{"name":"ardupilot-research","status":"connected","source":"dynamic"}]
"tools":[ … "mcp__ardupilot-research__lookup_param", … tổng 14 tool mcp__ardupilot-research__* ]
"apiKeySource":"none"
```

Lượt model kết thúc bằng `{"error":"authentication_failed","result":"Not logged in · Please run /login"}`
— lỗi **đăng nhập của client**, không liên quan server. Vì vậy: kết nối + liệt kê tool = **đã chứng
minh**; tool call do model = **vẫn chưa có bằng chứng** (UNVERIFIED).

### (g.2) Vì sao run1 ghi `status: failed` — scope đăng ký, không phải server

```powershell
cd <repo>; claude -p "hi" --output-format stream-json --verbose | Select-Object -First 1
# → "mcp_servers":[{"name":"ardupilot-research","status":"pending","source":"project"}], 0 tool mcp__*

claude mcp list
# ardupilot-research-test: … - √ Connected        (đăng ký --scope user)
# ardupilot-research:      … - ⏸ Pending approval  (project scope, chưa duyệt)
```

`enableAllProjectMcpServers: true` trong `.claude/settings.json` **và** `.claude/settings.local.json`
đều không đổi trạng thái `pending` trên `2.1.308` (đã đo cả hai, 0 tool). Kết luận: `.mcp.json`
project-scope phải được **duyệt một lần bằng TUI**; phiên headless không duyệt thì server **không được
spawn** và client chỉ báo trạng thái không kèm lý do — đúng lớp lỗi run1 ghi, không phải khiếm khuyết
của server. Cách chạy được, không cần duyệt tay: `--scope user`, hoặc
`--mcp-config <file> --strict-mcp-config`.

### (g.3) Tính tất định của khâu chấm run2

5 script chấm điểm chạy **hai lần** trên cùng raw run2 (`D:\Skill_tulan\bb-run2`):

| script | exit lần 1 | exit lần 2 | SHA-256 output lần 1 | lần 2 | kết luận |
|---|---|---|---|---|---|
| `verify_a_run2.py` | 0 | 0 | `FFA190EC2230FF83…` | `FFA190EC2230FF83…` | IDENTICAL |
| `verify_b.py` | 0 | 0 | `20C7FB5AF47B5D73…` | `20C7FB5AF47B5D73…` | IDENTICAL |
| `verify_cd.py` | 0 | 0 | `77399B0D22C0C690…` | `77399B0D22C0C690…` | IDENTICAL |
| `verify_e.py` | 0 | 0 | `289643AE92E8D5DB…` | `289643AE92E8D5DB…` | IDENTICAL |
| `verify_fg.py` | 0 | 0 | `83ACB46D90AA6BC5…` | `83ACB46D90AA6BC5…` | IDENTICAL |

Chi tiết + lệnh tái lập: `docs/blackbox/run2/determinism.md`. Giới hạn: đây là tất định của **khâu
chấm**, không phải của lần chạy server (run2 vẫn chỉ chạy đúng một lần theo luật).


### (g.4) Case H — tool call do model phát ra (OpenCode, model miễn phí)

Sau khi báo cáo này được viết, người dùng chỉ ra OpenCode có model miễn phí. Một phiên OpenCode
`v2.1.3`, model `opencode/deepseek-v4.1-flash-free`, đã chạy trọn:

```
tools["ardupilot-research"].lookup_param({ name_or_pattern: "RC_OPTIONS" })
  -> found: true, default: 32, cite_id: ardupilot#11fb2497e2a89d95
  -> URL: .../Copter-4.7.2/libraries/RC_Channel/RC_Channels_VarInfo.h#L84-L117
final answer: 32          (mỗi bước "cost":0)
```

Transcript thô: `docs/blackbox/h/opencode_stream.jsonl`. Cấu hình + lệnh: `docs/client-setup.md` §7.
Vì vậy case H chuyển từ NOT RUN sang PASS, và lỗi 8 chuyển từ PARTIAL sang FIXED: nguyên nhân gốc là
cách đăng ký (project scope chờ duyệt), không phải server.


### (g.5) run3 — chạy lại 108 case ba lần sau vòng cải tiến

Sau khi sửa bước chọn chunk (`docs/IMPROVEMENTS.md`), bộ case đóng băng chạy lại ba lần tại commit
`ea0a9d4`:

```
lần 1, 2, 3: 110 lần gọi, 116 file, cùng index 182,3 MB
payload giống nhau giữa ba lần: 110/110
điểm run3: 93 pass / 15 fail   (run2: 92 / 16), hồi quy: 0
C1: fail -> pass (excerpt chứa 0xD5, không còn 0xBA)
E: refused 11/11, info answered 4/4 · G1 20 mẫu · G2 20/20
```

Chi tiết + 17 payload khác run2: `docs/blackbox/run3/comparison.md`; raw và output 5 script chấm:
`docs/blackbox/run3/`.
