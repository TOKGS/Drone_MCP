"""Debug one query: show scores and identifier hits."""
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
from ardupilot_research_mcp import db, query  # noqa: E402

q = sys.argv[1] if len(sys.argv) > 1 else "RC_OPTIONS là tham số gì?"
con = db.connect()
payload = query.search(con, q, scope="all", limit=10)
print("expansions:", payload["expansions"])
for rank, item in enumerate(payload["results"], 1):
    text = con.execute("SELECT text FROM chunks WHERE cite_hash=?",
                       (item["cite_id"].split("#")[1],)).fetchone()["text"]
    print(f"{rank}. {item['score']:>9.2f}  RC_OPTIONS={text.count('RC_OPTIONS')}  "
          f"{item['source_id']}/{item['path']}")
