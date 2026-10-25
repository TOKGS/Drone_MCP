"""Print one real citation object (proof of the schema, not a mock)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ardupilot_research_mcp import cite, db  # noqa: E402

PATTERN = sys.argv[1] if len(sys.argv) > 1 else "crsf"

con = db.connect()
row = con.execute(
    "SELECT c.cite_hash, d.source_id FROM chunks c JOIN documents d ON d.id=c.document_id"
    " WHERE LOWER(d.path) LIKE ? ORDER BY c.id LIMIT 1", (f"%{PATTERN.lower()}%",)).fetchone()
if row is None:
    print(f"no chunk path matching {PATTERN!r}")
    raise SystemExit(2)

citation = cite.build_citation(con, cite.make_cite_id(row["source_id"], row["cite_hash"]))
keys = ("cite_id", "source_id", "repo", "ref", "channel", "unreleased", "version",
        "ingested_at", "url", "path", "lines", "tier", "license", "untrusted")
print(json.dumps({k: citation[k] for k in keys}, indent=2, ensure_ascii=False))
print(f"excerpt_len={len(citation['excerpt'])} "
      f"verify_quote={cite.verify_quote(con, citation['cite_id'], citation['excerpt'])}")
print("excerpt:")
print(citation["excerpt"][:300])
