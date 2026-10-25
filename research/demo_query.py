"""Demo: Vietnamese query expansion + distil effect, printed raw (no mocks)."""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from ardupilot_research_mcp import db, query  # noqa: E402

con = db.connect()

print("== index ==")
print(query.index_status(con)["counts"])

print("\n== distil effect (wiki chunks) ==")
row = con.execute(
    "SELECT AVG(LENGTH(c.distilled) * 1.0 / NULLIF(LENGTH(c.text), 0)) AS ratio,"
    "       COUNT(*) AS n FROM chunks c JOIN documents d ON d.id=c.document_id"
    " WHERE d.source_id='ardupilot_wiki'").fetchone()
print(f"wiki chunks={row['n']} mean(distilled/text)={row['ratio']:.3f}")

print("\n== Vietnamese query (glossary expansion) ==")
payload = query.search(con, "mất tín hiệu tay cầm", limit=3)
print("expansions:", payload["expansions"])
print("found:", payload["found"])
for item in payload["results"]:
    print(f"  {item['cite_id']}  {item['path']}  L{item['lines'][0]}-{item['lines'][1]}  "
          f"score={item['score']}")

print("\n== English query, code scope ==")
payload = query.search(con, "AP_RCPROTOCOL_ENABLED", scope="code", limit=3)
print("found:", payload["found"])
for item in payload["results"]:
    print(f"  {item['cite_id']}  {item['path']}  score={item['score']}")

print("\n== out-of-corpus question must return found:false ==")
payload = query.search(con, "how do I bake sourdough bread", limit=3)
print("found:", payload["found"], "| note:", payload["note"], "| results:", len(payload["results"]))
