"""Citation identity and quote verification.

cite_id must be content-addressed (stable across re-ingest, independent of row ids),
pinned to a SHA, and every excerpt must be a verbatim substring of the stored chunk.
"""

from __future__ import annotations

import hashlib
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from ardupilot_research_mcp import cite, db  # noqa: E402
from ardupilot_research_mcp.ingest import build  # noqa: E402

SOURCE = {
    "id": "demo", "repo": "acme/demo", "ref": "deadbeefcafe",
    "ref_kind": "commit", "version_label": "demo@deadbee",
    "tier": "T1", "license": "MIT",
}
TEXT = "# Pin map\n\nSERIAL1_PROTOCOL must be set before the RC protocol is probed.\n"


def _index(tmp: Path) -> Path:
    root = tmp / "corpus"
    (root / "demo").mkdir(parents=True)
    (root / "demo" / "doc.md").write_text(TEXT, encoding="utf-8")
    path = tmp / "index.sqlite"
    con = db.init(path)
    build.ingest_source(con, SOURCE, root, manifest=None)
    con.close()
    return path


def test_hash_is_content_addressed() -> None:
    text_sha = hashlib.sha256(b"same text").hexdigest()
    a = cite.compute_cite_hash("s1", "a/b.md", 1, 4, text_sha)
    b = cite.compute_cite_hash("s1", "a/b.md", 1, 4, text_sha)
    assert a == b
    assert len(a) == cite.CITE_HASH_CHARS
    assert a != cite.compute_cite_hash("s1", "a/b.md", 1, 5, text_sha)
    assert a != cite.compute_cite_hash("s2", "a/b.md", 1, 4, text_sha)
    assert a != cite.compute_cite_hash("s1", "a/c.md", 1, 4, text_sha)


def test_cite_id_roundtrip_and_rejects() -> None:
    digest = cite.compute_cite_hash("demo", "doc.md", 1, 2, "x" * 64)
    cite_id = cite.make_cite_id("demo", digest)
    assert cite.parse_cite_id(cite_id) == ("demo", digest)
    for bad in ("demo", "demo#", "demo#zzzz", "demo#c000123"):
        try:
            cite.parse_cite_id(bad)
        except ValueError:
            continue
        raise AssertionError(f"{bad!r} should be rejected")


def test_citation_fields_are_pinned_and_verbatim() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        con = db.connect(_index(Path(tmp)))
        row = con.execute("SELECT c.cite_hash, c.text FROM chunks c").fetchone()
        cite_id = cite.make_cite_id("demo", row["cite_hash"])
        built = cite.build_citation(con, cite_id)
        assert built["cite_id"] == cite_id
        assert built["url"].startswith("https://github.com/acme/demo/blob/deadbeefcafe/")
        assert "/blob/main/" not in built["url"] and "/blob/master/" not in built["url"]
        assert built["license"] == "MIT" and built["tier"] == "T1"
        assert built["untrusted"] is True
        assert len(built["excerpt"]) <= cite.EXCERPT_CHARS
        assert built["excerpt"] in row["text"]
        assert built["lines"][1] >= built["lines"][0] >= 1
        con.close()


def test_verify_quote_true_and_false() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        con = db.connect(_index(Path(tmp)))
        row = con.execute("SELECT c.cite_hash, c.text FROM chunks c").fetchone()
        cite_id = cite.make_cite_id("demo", row["cite_hash"])
        assert cite.verify_quote(con, cite_id, row["text"][:20])
        assert not cite.verify_quote(con, cite_id, "text that is not in the chunk")
        assert not cite.verify_quote(con, "demo#0000000000000000", "anything")
        con.close()


def test_cite_ids_are_stable_across_reingest() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        first = db.connect(_index(tmp / "a")) if (tmp / "a").mkdir() is None else None
        ids_first = {r["cite_hash"] for r in first.execute("SELECT cite_hash FROM chunks")}
        con_first = first
        con_first.close()
        second_path = _index(tmp / "b")
        con_second = db.connect(second_path)
        ids_second = {r["cite_hash"] for r in con_second.execute("SELECT cite_hash FROM chunks")}
        con_second.close()
        assert ids_first == ids_second and ids_first
