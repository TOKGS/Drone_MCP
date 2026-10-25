#!/usr/bin/env python3
"""Shallow clones at the pinned ref, so citations can be audited against real Git blobs.

Zero search quota. Works around this machine's schannel failure by forcing the openssl
TLS backend for the git process only.

    python -m research.clone [--only ID]
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
GIT_DIR = REPO / "research" / "cache" / "git"


def git(args: list[str], cwd: Path | None = None) -> tuple[int, str]:
    # schannel fails in this environment (SEC_E_NO_CREDENTIALS); the openssl backend with
    # verification off is the only working transport. -c is honoured, env vars are not.
    common = ["-c", "http.sslBackend=openssl", "-c", "http.sslVerify=false"]
    env = dict(os.environ, GIT_TERMINAL_PROMPT="0")
    proc = subprocess.run(["git", *common, *args], cwd=str(cwd) if cwd else None,
                          capture_output=True, text=True, env=env)
    return proc.returncode, (proc.stdout + proc.stderr).strip()


def head(clone: Path) -> str | None:
    code, out = git(["rev-parse", "HEAD"], cwd=clone)
    return out if code == 0 else None


def ensure(source: dict) -> dict:
    source_id, ref = source["id"], source["ref"]
    url = f"https://github.com/{source['repo']}.git"
    clone = GIT_DIR / source_id
    result = {"id": source_id, "ref": ref, "path": str(clone)}
    if clone.exists():
        current = head(clone)
        result.update({"status": "exists", "head": current})
        return result

    GIT_DIR.mkdir(parents=True, exist_ok=True)
    if source["ref_kind"] == "tag":
        code, out = git(["clone", "--depth", "1", "--branch", ref, "--quiet", url, str(clone)])
        result["status"] = "cloned" if code == 0 else "clone-failed"
        if code != 0:
            result["error"] = out[-400:]
            return result
    else:
        code, out = git(["init", "--quiet", str(clone)])
        if code != 0:
            result.update({"status": "init-failed", "error": out[-400:]})
            return result
        git(["remote", "add", "origin", url], cwd=clone)
        code, out = git(["fetch", "--depth", "1", "--quiet", "origin", ref], cwd=clone)
        if code != 0:
            result.update({"status": "fetch-failed", "error": out[-400:]})
            return result
        code, out = git(["checkout", "--quiet", "FETCH_HEAD"], cwd=clone)
        if code != 0:
            result.update({"status": "checkout-failed", "error": out[-400:]})
            return result
        result["status"] = "cloned"

    result["head"] = head(clone)
    if source["ref_kind"] == "tag":
        code, tag_sha = git(["rev-parse", f"refs/tags/{ref}^{{commit}}"], cwd=clone)
        result["pin_match"] = code == 0 and tag_sha.strip() == result["head"]
        result["tag_commit"] = tag_sha.strip() if code == 0 else None
    else:
        result["pin_match"] = result["head"] == ref
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", default=None)
    args = parser.parse_args(argv)

    conf = yaml.safe_load((REPO / "sources.yaml").read_text(encoding="utf-8"))
    failures = 0
    for source in conf["sources"]:
        if args.only and source["id"] != args.only:
            continue
        if not source.get("repo"):
            print(f"{source['id']:<18} skipped (no repo: local/unpinned source)")
            continue
        info = ensure(source)
        state = info.get("status")
        print(f"{info['id']:<18}{state:<16}head={str(info.get('head'))[:16]:<18}"
              f"pin_match={info.get('pin_match')}")
        if state not in ("exists", "cloned") or info.get("pin_match") is False:
            failures += 1
            if info.get("error"):
                print(f"  error: {info['error'][:200]}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
