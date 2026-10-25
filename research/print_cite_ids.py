"""Print real cite_ids for the chunks the example scripts derive from."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from ardupilot_research_mcp import cite, db  # noqa: E402

TARGETS = [
    ("crsf_spec", "crsf.md", "CRC"),
    ("expresslrs", "crsf_protocol.h", None),
    ("crsf_spec", "crsf.md", "0x16"),
    ("ardupilot", "make_intel_hex.py", None),
    ("ardupilot", "RC_Channels_VarInfo.h", "_OPTIONS"),
]

con = db.connect()
out = {}
for source_id, path_fragment, needle in TARGETS:
    sql = ("SELECT c.cite_hash, d.path, c.line_start, c.line_end FROM chunks c"
           " JOIN documents d ON d.id = c.document_id"
           " WHERE d.source_id = ? AND d.path LIKE ?")
    params: list[object] = [source_id, f"%{path_fragment}%"]
    if needle:
        sql += " AND (c.heading_path LIKE ? OR c.text LIKE ?)"
        params.extend([f"%{needle}%", f"%{needle}%"])
    sql += " ORDER BY c.line_start LIMIT 1"
    row = con.execute(sql, params).fetchone()
    if row is None:
        out[f"{source_id}:{path_fragment}"] = None
        continue
    cite_id = cite.make_cite_id(source_id, row["cite_hash"])
    citation = cite.build_citation(con, cite_id)
    out[f"{source_id}:{path_fragment}"] = {
        "cite_id": cite_id, "path": row["path"],
        "lines": [row["line_start"], row["line_end"]], "url": citation["url"],
    }
print(json.dumps(out, indent=2, ensure_ascii=False))
