#!/usr/bin/env python3
"""Locate and fetch the MCP registration docs inside each client repo.

GitHub trees API costs 1 metered call per repo (github provider); the files themselves are raw
downloads at zero search quota. Everything is recorded in the ledger.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

import research.fetch as fetch  # noqa: E402

REPOS = {"claude-code": "anthropics/claude-code",
         "opencode": "sst/opencode",
         "codex": "openai/codex"}
INTERESTING = re.compile(r"mcp", re.I)
OUT = REPO / "research" / "cache" / "clients"


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    summary: dict = {}
    for name, slug in REPOS.items():
        repo = fetch.api_json(f"/repos/{slug}")
        branch = repo.get("default_branch", "main")
        tree = fetch.api_json(f"/repos/{slug}/git/trees/{branch}?recursive=1")
        paths = [item["path"] for item in tree.get("tree", []) if item["type"] == "blob"]
        mcp_paths = [path for path in paths
                     if INTERESTING.search(path) and path.lower().endswith((".md", ".mdx", ".toml", ".json"))]
        # prefer documentation over source code
        mcp_paths.sort(key=lambda path: (0 if ("docs" in path.lower() or "readme" in path.lower()) else 1,
                                         len(path)))
        saved = []
        for relative in mcp_paths[:6]:
            url = f"https://raw.githubusercontent.com/{slug}/{branch}/{relative}"
            target = OUT / f"{name}-{relative}".replace("/", "_")
            try:
                meta = fetch.download("github", "raw", url, target)
                saved.append({"file": relative, "bytes": meta["bytes"]})
            except Exception as exc:  # noqa: BLE001
                saved.append({"file": relative, "error": str(exc)[:80]})
        summary[name] = {"repo": slug, "branch": branch,
                         "tree_size": len(paths), "mcp_paths": mcp_paths[:20], "saved": saved}
        print(f"{name:<12} tree={len(paths):<6} mcp_docs={len(mcp_paths):<3} saved={[s['file'] for s in saved]}")
    (OUT / "tree-manifest.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
