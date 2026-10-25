"""Ingest CLI: ardupilot-research-ingest --all | --source ID | --rebuild-index | --verify."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from .. import config, db
from . import build


def _sources(only: str | None) -> list[dict]:
    sources = config.load_sources()["sources"]
    if only:
        picked = [s for s in sources if s["id"] == only]
        if not picked:
            raise SystemExit(f"unknown source {only!r}; known: {[s['id'] for s in sources]}")
        return picked
    return sources


def _ingest(con, sources: list[dict], root: Path, resume: bool) -> None:
    total = {"files": 0, "chunks": 0, "skipped": 0}
    for source in sources:
        # local-project lives in data/local (no archive, no pin); everything else in the corpus.
        source_root = config.data_dir() / "local" if source.get("ref_kind") == "local" else root
        if not (source_root / source["id"]).exists() and source.get("ref_kind") == "local":
            print(f"{source['id']:<16} skipped: no files under {source_root} "
                  f"(drop your board files in {source_root / source['id']})")
            continue
        manifest = build.load_manifest(source["id"])
        stats = build.ingest_source(con, source, source_root, manifest=manifest, resume=resume)
        total["files"] += stats["files"]
        total["chunks"] += stats["chunks"]
        total["skipped"] += stats["skipped"]
        print(f"{stats['source']:<16} files={stats['files']:<5} chunks={stats['chunks']:<6} "
              f"skipped={stats['skipped']:<5} filtered={stats['filtered']:<5} "
              f"binary={stats['binary']:<4} {stats['bytes'] / 1048576:6.1f}MB {stats['elapsed_s']}s")
    db.rebuild_fts(con)
    con.execute("INSERT OR REPLACE INTO build_state (key, value) VALUES ('last_ingest', ?)",
                (time.strftime("%Y-%m-%dT%H:%M:%S%z"),))
    print(f"\ntotal files={total['files']} chunks={total['chunks']} skipped={total['skipped']}")
    print("counts:", json.dumps(db.counts(con), ensure_ascii=False))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="ardupilot-research-ingest")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--all", action="store_true", help="ingest every pinned source")
    group.add_argument("--source", metavar="ID", help="ingest one source id")
    group.add_argument("--verify", action="store_true", help="structural checks over the index")
    parser.add_argument("--rebuild-index", action="store_true",
                        help="delete index.sqlite first (combine with --all or --source)")
    parser.add_argument("--resume", action="store_true", default=True,
                        help="skip files whose sha is already indexed (default)")
    parser.add_argument("--no-resume", dest="resume", action="store_false")
    parser.add_argument("--offline-dir", metavar="PATH",
                        help="corpus root to read instead of data/corpus")
    args = parser.parse_args(argv)

    if args.verify:
        if not config.index_exists():
            print("index not built: run --all first", file=sys.stderr)
            return 2
        con = db.connect()
        checks = build.verify_index(con)
        print(json.dumps({"checks": checks, "counts": db.counts(con)}, indent=2))
        bad = {key: value for key, value in checks.items() if value}
        if bad:
            print(f"FAIL {bad}", file=sys.stderr)
            return 1
        print("verify: PASS")
        return 0

    if args.rebuild_index:
        for suffix in ("", "-wal", "-shm"):
            Path(str(config.index_path()) + suffix).unlink(missing_ok=True)

    root = Path(args.offline_dir) if args.offline_dir else config.corpus_root()
    if not root.exists():
        print(f"corpus root missing: {root}", file=sys.stderr)
        return 2

    con = db.init()
    try:
        _ingest(con, _sources(args.source), root, args.resume)
    finally:
        con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
