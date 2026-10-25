#!/usr/bin/env python3
"""Source audit: what is pinned, licensed, present on disk, and how many chunks it produced."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

import yaml  # noqa: E402

from ardupilot_research_mcp import config, db  # noqa: E402

REQUIRED = {
    "ardupilot": "ArduPilot source",
    "ardupilot_wiki": "ArduPilot wiki (dev + user docs)",
    "mavlink": "MAVLink XML definitions",
    "expresslrs": "ExpressLRS source",
    "expresslrs_docs": "ExpressLRS Docs",
    "crsf_spec": "CRSF working-group spec",
    "edgetx": "EdgeTX source",
}


def main() -> int:
    conf = yaml.safe_load(config.sources_path().read_text(encoding="utf-8"))
    by_id = {s["id"]: s for s in conf["sources"]}
    con = db.connect()
    chunk_counts = {
        row["id"]: row["n"]
        for row in con.execute(
            "SELECT d.source_id AS id, COUNT(c.id) AS n FROM documents d"
            " LEFT JOIN chunks c ON c.document_id=d.id GROUP BY d.source_id")
    }

    print(f"{'source_id':<17}{'url':<46}{'tier':<5}{'license':<26}{'pin':<18}{'chunks':>7}")
    for source_id, label in REQUIRED.items():
        source = by_id.get(source_id)
        if source is None:
            print(f"{source_id:<17}{'MISSING (not in sources.yaml)':<46}"
                  f"{'-':<5}{'-':<26}{'-':<18}{0:>7}")
            continue
        url = f"https://github.com/{source['repo']}"
        pin = source["ref"][:16]
        license_short = str(source.get("license", "?"))[:24]
        print(f"{source_id:<17}{url:<46}{source.get('tier', '?'):<5}{license_short:<26}"
              f"{pin:<18}{chunk_counts.get(source_id, 0):>7}")

    print("\n== per-source evidence on disk ==")
    for source in conf["sources"]:
        root = config.corpus_root() / source["id"]
        manifest = config.corpus_root() / f"{source['id']}.manifest.json"
        files = sum(1 for _ in root.rglob("*") if _.is_file()) if root.exists() else 0
        meta = json.loads(manifest.read_text(encoding="utf-8")) if manifest.exists() else {}
        print(f"{source['id']:<17} files_on_disk={files:<6} manifest_ref={meta.get('ref', '?')[:16]:<18}"
              f" manifest_sha={str(meta.get('manifest_sha256', ''))[:16]}")

    print("\n== known gaps (evidence) ==")
    print("crsf_spec      : https://github.com/tbs-fpv/CRSF -> HTTP 404 during Wave-1 probe; "
          "not pinned, not indexed (CRSF behaviour is covered by ExpressLRS/EdgeTX T1 source)")
    print("expresslrs_docs: repository not resolved during this checkpoint; "
          "expresslrs.org docs are NOT in the corpus (MISSING)")
    print("ardupilot/wiki : wiki dev+user present; 'issues/PR' (T2) and forum (T3) NOT ingested")
    return 0


if __name__ == "__main__":
    sys.exit(main())
