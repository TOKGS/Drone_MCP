"""Investigate the one citation-sample mismatch and the ledger schema."""

import random
import sqlite3
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
from ardupilot_research_mcp import cite, db  # noqa: E402

con = db.connect()
rows = con.execute("SELECT source_id, cite_hash, path, line_start, line_end, text FROM chunks"
                   " JOIN documents ON documents.id = chunks.document_id").fetchall()
rng = random.Random(42)
for index, row in enumerate(rng.sample(rows, 10), start=1):
    blob = subprocess.run(["git", "-C", f"research/cache/git/{row['source_id']}", "show",
                           f"HEAD:{row['path']}"], capture_output=True, text=True)
    if blob.returncode != 0:
        print(f"{index}: git show failed for {row['path']}: {blob.stderr.strip()[:120]}")
        continue
    lines = blob.stdout.splitlines()
    slice_ = "\n".join(lines[row["line_start"] - 1:row["line_end"]])
    same = slice_.strip() == row["text"].strip()
    print(f"{index}: {row['source_id']:<14}{row['path'][:50]:<52}L{row['line_start']}-{row['line_end']}"
          f" same={same} clone_lines={len(lines)} chunk_lines={len(row['text'].splitlines())}")
    if not same:
        for offset in range(0, 3):
            a = slice_.splitlines()
            b = row["text"].splitlines()
            if offset < len(a) and offset < len(b):
                print(f"   git[{offset}]={a[offset][:90]!r}")
                print(f"   db [{offset}]={b[offset][:90]!r}")
        diff_at = next((i for i, (x, y) in enumerate(zip(slice_.splitlines(), row["text"].splitlines()))
                        if x != y), None)
        print(f"   first differing line: {diff_at}")
con.close()

print("\n=== governor ledger schema ===")
ledger = REPO / "research" / "ledger.sqlite"
if ledger.exists():
    raw = sqlite3.connect(ledger)
    for name, sql in raw.execute("SELECT name, sql FROM sqlite_master WHERE type='table'").fetchall():
        print(f"table {name}: {sql}")
    raw.close()
else:
    print("ledger missing")

print("\n=== hardcoded X.Y.Z literals in src/ ===")
import re  # noqa: E402
for path in sorted((REPO / "src").rglob("*.py")):
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if re.search(r"\b\d+\.\d+\.\d+\b", line) and "Copter-" not in line:
            print(f"{path.relative_to(REPO)}:{number}: {line.strip()[:110]}")
