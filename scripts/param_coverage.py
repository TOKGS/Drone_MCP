#!/usr/bin/env python3
"""Which directories declare `// @Param` blocks at the pin, and does sources.yaml copy them?

Reads the pinned clone through `git ls-tree` / `git show HEAD:<path>`, not the extracted corpus,
so a directory the allowlist currently drops is still counted. Prints a per-directory table
(files, @Param blocks, allowlist verdict) and the ratio against the built params table.

    python scripts/param_coverage.py [--git-dir PATH] [--json]
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

PARAM_BLOCK = re.compile(r"^\s*//\s*@Param[:\{]")
CODE_SUFFIXES = (".cpp", ".h")
SCOPES = ("ArduCopter/", "libraries/")


def git(git_dir: Path, *args: str) -> str:
    done = subprocess.run(["git", "-C", str(git_dir), *args], capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    if done.returncode != 0:
        raise SystemExit(f"git {' '.join(args)} failed: {done.stderr.strip()}")
    return done.stdout


def allowlist() -> list[str]:
    import yaml

    conf = yaml.safe_load((REPO / "sources.yaml").read_text(encoding="utf-8"))
    for source in conf["sources"]:
        if source["id"] == "ardupilot":
            return list(source.get("include", []) or [])
    raise SystemExit("sources.yaml has no ardupilot source")


def params_in_index() -> int | None:
    from ardupilot_research_mcp import config, db

    if not config.index_exists():
        return None
    con = db.connect()
    try:
        return con.execute("SELECT COUNT(*) FROM params").fetchone()[0]
    except Exception:
        return None
    finally:
        con.close()


def shipped_names(git_dir: Path) -> tuple[list[str], int]:
    """Every first-token parameter name in the shipped default/frame parameter files."""
    listing = git(git_dir, "ls-tree", "-r", "--name-only", "HEAD",
                  "Tools/autotest/default_params", "Tools/Frame_params").splitlines()
    names: set[str] = set()
    files = 0
    for rel in listing:
        if not rel.endswith((".param", ".parm")):
            continue
        files += 1
        for line in git(git_dir, "show", f"HEAD:{rel}").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            token = re.split(r"[,\s]+", line, maxsplit=1)[0].strip()
            if token:
                names.add(token.upper())
    return sorted(names), files


def classify_missing(con, name: str, payload: dict) -> str:
    hint = payload.get("renamed_hint")
    if hint:
        return f"renamed at pin -> {hint['new']} ({hint['path']}:{hint['lines'][0]})"
    for suffix in (name, name.split("_", 1)[-1]):
        row = con.execute("SELECT param_name FROM params WHERE name_suffix = ?"
                          " AND param_name != ? LIMIT 1", (suffix, name)).fetchone()
        if row:
            return f"same suffix declared under another prefix ({row['param_name']})"
    return "no @Param block in the Copter corpus declares it (other vehicle's parameter)"


def names_report(git_dir: Path) -> int:
    from ardupilot_research_mcp import db
    from ardupilot_research_mcp.tools.lookup_param import lookup_param

    names, files = shipped_names(git_dir)
    con = db.connect()
    # The MCP wrapper rate-limits to 60 calls/min; this report asks about every shipped name.
    lookup = getattr(lookup_param, "__wrapped__", lookup_param)
    missing: list[tuple[str, str]] = []
    found = 0
    try:
        for name in names:
            payload = lookup(con, name)
            if payload["found"]:
                found += 1
            else:
                missing.append((name, classify_missing(con, name, payload)))
    finally:
        con.close()
    print(f"names in {files} shipped parameter files: {len(names)}")
    print(f"found by lookup_param: {found}/{len(names)} "
          f"({100.0 * found / len(names) if names else 0:.1f}%)")
    print(f"not found: {len(missing)}")
    for name, reason in missing:
        print(f"  {name:<34} {reason}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--git-dir", default=str(REPO / "research" / "cache" / "git" / "ardupilot"))
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--names", action="store_true",
                        help="check every name in the shipped parameter files with lookup_param")
    args = parser.parse_args(argv)

    git_dir = Path(args.git_dir)
    if args.names:
        return names_report(git_dir)
    patterns = allowlist()
    documents = [rel for rel in git(git_dir, "ls-tree", "-r", "--name-only", "HEAD").splitlines()
                 if rel.endswith(CODE_SUFFIXES) and rel.startswith(SCOPES)]

    per_dir: dict[str, dict] = {}
    for rel in documents:
        dir_key = "/".join(rel.split("/")[:2]) if rel.startswith("libraries/") \
            else rel.split("/")[0]
        entry = per_dir.setdefault(dir_key, {"files": 0, "allowed": 0, "param_blocks": 0})
        text = git(git_dir, "show", f"HEAD:{rel}")
        blocks = sum(1 for line in text.splitlines() if PARAM_BLOCK.match(line))
        entry["files"] += 1
        entry["allowed"] += 1 if any(fnmatch.fnmatch(rel, pat) for pat in patterns) else 0
        entry["param_blocks"] += blocks

    rows = sorted(((key, value) for key, value in per_dir.items() if value["param_blocks"]),
                  key=lambda item: (-item[1]["param_blocks"], item[0]))
    total_blocks = sum(value["param_blocks"] for _, value in rows)
    total_blocked = sum(value["param_blocks"] for _, value in rows
                        if value["allowed"] == 0)
    db_params = params_in_index()

    def verdict(value: dict) -> str:
        if value["allowed"] == value["files"]:
            return "y"
        return "part" if value["allowed"] else "n"

    if args.json:
        print(json.dumps({"dirs": [{"dir": key, **value, "in_allowlist": verdict(value)}
                                   for key, value in rows],
                          "param_blocks_in_scope": total_blocks,
                          "param_blocks_blocked": total_blocked,
                          "params_in_index": db_params}, indent=2))
        return 0

    print(f"{'directory':<34} {'files':>5} {'@Param':>7} {'allow.':>7}")
    for key, value in rows:
        print(f"{key:<34} {value['files']:>5} {value['param_blocks']:>7} {verdict(value):>7}")
    print(f"{'TOTAL (ArduCopter + libraries)':<34} {len(documents):>5} {total_blocks:>7}")
    print(f"@Param blocks in directories the allowlist drops entirely: {total_blocked}")
    print(f"@Param blocks in scoped directories: {total_blocks}")
    if db_params is None:
        print("params in index: index not built")
    else:
        print(f"params in index: {db_params}")
        ratio = 100.0 * db_params / total_blocks if total_blocks else 0.0
        print(f"ratio params/@Param blocks: {ratio:.2f}%")
    return 0


if __name__ == "__main__":
    sys.exit(main())
