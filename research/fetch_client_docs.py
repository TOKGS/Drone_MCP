#!/usr/bin/env python3
"""Fetch the CURRENT MCP registration docs for OpenCode / Claude Code / Codex.

Cost ladder step 2: repository default branch via one metered API call per repo, then raw files
at zero search quota. Everything lands in research/cache/clients/ and is cited in the README.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

import research.fetch as fetch  # noqa: E402

REPOS = {
    "claude-code": {"repo": "anthropics/claude-code",
                    "files": ["README.md", "docs/mcp.md", "MCP.md"]},
    "opencode": {"repo": "sst/opencode",
                 "files": ["README.md", "docs/mcp.md", "packages/web/src/content/docs/mcp.mdx"]},
    "codex": {"repo": "openai/codex",
              "files": ["README.md", "docs/advanced.md", "docs/config.md"]},
}
OUT = REPO / "research" / "cache" / "clients"


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    manifest: dict = {}
    for name, spec in REPOS.items():
        try:
            repo = fetch.api_json(f"/repos/{spec['repo']}")
        except Exception as exc:  # noqa: BLE001
            print(f"{name}: repo lookup failed: {exc}")
            manifest[name] = {"repo": spec["repo"], "error": str(exc)[:160]}
            continue
        branch = repo.get("default_branch", "main")
        saved = []
        for relative in spec["files"]:
            url = f"https://raw.githubusercontent.com/{spec['repo']}/{branch}/{relative}"
            try:
                meta = fetch.download("github", "raw", url, OUT / f"{name}-{relative}".replace("/", "_"))
                saved.append({"file": relative, "bytes": meta["bytes"]})
            except Exception as exc:  # noqa: BLE001 - a missing file is a normal answer
                saved.append({"file": relative, "error": str(exc)[:80]})
        manifest[name] = {"repo": spec["repo"], "branch": branch,
                          "commit": repo.get("pushed_at"), "saved": saved}
        print(f"{name:<12} branch={branch:<8} " +
              ", ".join(f"{item['file']}={item.get('bytes', item.get('error'))}" for item in saved))
    (OUT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"\nwritten {OUT / 'manifest.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
