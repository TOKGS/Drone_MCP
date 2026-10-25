#!/usr/bin/env python3
"""Extract the pinned corpus from cached tarballs, filtered by sources.yaml.

Zero network. Copies only text/code members that match a source's include rules,
writes `data/corpus/<id>/...`, copies the license file to `docs/licenses/`, and
records a per-source manifest (file list digest + counts) under `data/corpus/`.

Usage:  python -m research.extract [--only ID] [--force]
"""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import sys
import tarfile
import time
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCES = REPO_ROOT / "sources.yaml"


def load_sources() -> dict:
    with open(SOURCES, "r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def _match_any(rel: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatch(rel, pattern) for pattern in patterns)


def _safe_rel(name: str) -> str | None:
    parts = name.split("/")
    if not parts or parts[0] in ("", ".", ".."):
        return None
    if any(part == ".." for part in parts):
        return None
    return "/".join(parts)


def extract_source(source: dict, conf: dict, tarball: Path, *, force: bool) -> dict:
    source_id = source["id"]
    dest_root = REPO_ROOT / conf["corpus_root"] / source_id
    manifest_path = REPO_ROOT / conf["corpus_root"] / f"{source_id}.manifest.json"
    if manifest_path.exists() and dest_root.exists() and not force:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("ref") == source["ref"]:
            print(f"{source_id:<16} cached  files={manifest['files']:<6} "
                  f"{manifest['bytes'] / 1048576:.1f}MB")
            return manifest

    if not tarball.exists():
        raise FileNotFoundError(f"missing tarball {tarball}; run research.fetch download {source_id}")

    dest_root.mkdir(parents=True, exist_ok=True)
    licenses_dir = REPO_ROOT / conf["licenses_dir"]
    licenses_dir.mkdir(parents=True, exist_ok=True)

    excludes = source.get("exclude", []) or []
    includes = source.get("include", []) or []
    exclude_ext = set(conf.get("exclude_ext", []))
    always = set(conf.get("always_include", []))

    files = bytes_written = 0
    by_ext: dict[str, int] = {}
    entries: list[str] = []
    license_copied = None
    started = time.perf_counter()

    with tarfile.open(tarball) as archive:
        for member in archive:
            if not member.isfile():
                continue
            raw = member.name.split("/", 1)
            if len(raw) != 2:
                continue
            rel = _safe_rel(raw[1])
            if rel is None:
                continue
            suffix = Path(rel).suffix.lower()
            basename = Path(rel).name
            keep = basename in always or (_match_any(rel, includes) if includes else True)
            if keep and _match_any(rel, excludes):
                keep = False
            if keep and suffix in exclude_ext:
                keep = False
            if not keep:
                continue
            target = dest_root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            handle = archive.extractfile(member)
            if handle is None:
                continue
            data = handle.read()
            target.write_bytes(data)
            files += 1
            bytes_written += len(data)
            by_ext[suffix or "(none)"] = by_ext.get(suffix or "(none)", 0) + len(data)
            entries.append(f"{rel}:{len(data)}")
            if license_copied is None and basename.upper().startswith(("LICENSE", "COPYING")):
                license_copied = rel
                (licenses_dir / f"{source_id}-{basename}").write_bytes(data)

    entries.sort()
    manifest = {
        "id": source_id,
        "repo": source["repo"],
        "ref": source["ref"],
        "ref_kind": source["ref_kind"],
        "version_label": source.get("version_label"),
        "tier": source.get("tier"),
        "license": source.get("license"),
        "extracted_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "files": files,
        "bytes": bytes_written,
        "by_ext": by_ext,
        "license_copied": license_copied,
        "manifest_sha256": hashlib.sha256("\n".join(entries).encode()).hexdigest(),
        "elapsed_s": round(time.perf_counter() - started, 1),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
                             encoding="utf-8")
    print(f"{source_id:<16} files={files:<6} {bytes_written / 1048576:7.1f}MB "
          f"license={license_copied} {manifest['elapsed_s']}s")
    return manifest


def download_meta() -> dict:
    path = REPO_ROOT / "research" / "downloads.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", default=None)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)

    conf = load_sources()
    meta = download_meta()
    cache = REPO_ROOT / "research" / "cache" / "repos"
    total_files = total_bytes = 0
    for source in conf["sources"]:
        if args.only and args.only != source["id"]:
            continue
        # The local overlay has no tarball by design; ingest reads it from data/local, so
        # extraction skips it instead of failing the build.
        if source.get("ref_kind") == "local":
            print(f"{source['id']:<16} skipped (local source, no tarball; ingest reads data/local)")
            continue
        tarball = cache / f"{source['id']}.tar.gz"
        if source["id"] in meta and meta[source["id"]].get("sha256"):
            source = dict(source)
        manifest = extract_source(source, conf, tarball, force=args.force)
        total_files += manifest["files"]
        total_bytes += manifest["bytes"]
        if manifest.get("ref") != source["ref"]:
            print(f"  ! pin drift for {source['id']}: manifest={manifest.get('ref')} "
                  f"yaml={source['ref']} (re-run with --force)")
    print(f"\ncorpus total: {total_files} files, {total_bytes / 1048576:.1f}MB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
