"""Query-level tests that pin the behaviour mutation testing relies on."""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(os.environ.get("ARM_SRC", REPO / "src"))))

from ardupilot_research_mcp import config, db, query  # noqa: E402

pytestmark = pytest.mark.skipif(not config.index_exists(), reason="index not built")


@pytest.fixture()
def con():
    connection = db.connect()
    yield connection
    connection.close()


def test_out_of_corpus_question_is_not_answered() -> None:
    con = db.connect()
    try:
        payload = query.search(con, "how do I bake sourdough bread")
        assert payload["found"] is False
        assert payload["results"] == []
        assert "nothing was invented" in payload["note"]
    finally:
        con.close()


def test_scope_without_sources_says_so() -> None:
    con = db.connect()
    try:
        payload = query.search(con, "failsafe", scope="forum")
        assert payload["found"] is False
        assert "no indexed source" in payload["note"]
    finally:
        con.close()


def test_identifier_query_prefers_the_named_page() -> None:
    con = db.connect()
    try:
        payload = query.search(con, "RC_OPTIONS", limit=3)
        assert payload["found"] is True
        paths = [item["path"] for item in payload["results"]]
        assert any("common-rc-options" in path for path in paths), paths
    finally:
        con.close()


def test_vietnamese_query_is_expanded() -> None:
    con = db.connect()
    try:
        payload = query.search(con, "mất tín hiệu tay cầm", limit=3)
        assert payload["expansions"], "glossary expansion must fire"
        assert payload["found"] is True
    finally:
        con.close()


# --- fix/C, lỗi 5a: glossary must match whole tokens, never a word fragment ----------------

GLOSSARY_MUST_NOT_FIRE = [
    "giá bitcoin hôm nay",
    "orbit height",
    "habit tracker",
    "habit tracking app for hikers",
    "how many bits are in a byte",
    "bitcoin mining rig review",
    "arbitrary bits in a register",
    "orbit",
    "bitmask của LOG_BITMASK",
]

GLOSSARY_MUST_FIRE = [
    ("bit nào của LOG_BITMASK bật imu", "bit -> bitmask/bit"),
    ("mặt nạ bit của RC_OPTIONS", "mặt nạ bit -> bitmask"),
    ("kênh 3 của CRSF dùng làm gì", "kênh -> channel"),
    ("tần số 915 MHz có hợp lệ không", "tần số -> frequency/rate"),
    ("cảm biến rung có ảnh hưởng gì", "cảm biến rung -> vibration/accelerometer/accel"),
    ("không arm được sau khi nạp firmware", "không arm được -> arming failure/prearm check/arm"),
]


def test_glossary_does_not_match_a_fragment_of_a_word(con) -> None:
    for text in GLOSSARY_MUST_NOT_FIRE:
        payload = query.search(con, text, limit=3)
        assert payload["expansions"] == [], (text, payload["expansions"])
        assert payload["query_expanded"] is None, text


def test_glossary_matches_whole_tokens_and_multiword_phrases(con) -> None:
    for text, expected in GLOSSARY_MUST_FIRE:
        payload = query.search(con, text, limit=3)
        assert expected in payload["expansions"], (text, payload["expansions"])
        assert payload["query_expanded"], text


# --- fix/C, lỗi 5b: out-of-scope flags (foreign product, unknown version, weak match) -----

FOREIGN_PRODUCTS = [
    ("cách chỉnh EKF2 trên PX4", "PX4"),
    ("Betaflight PID tuning", "Betaflight"),
    ("iNav waypoint mission setup", "iNav"),
    ("KISS flight controller firmware", "KISS"),
    ("Cleanflight CLI commands", "Cleanflight"),
    ("cách cài đặt QGroundControl", "QGroundControl"),
]

UNRELATED_TOPICS = [
    "giá ethereum hôm nay",
    "công thức nấu phở bò",
    "thời tiết Hà Nội ngày mai",
    "giá vàng hôm nay",
    "cách làm bánh mì",
    "đội hình bóng đá tối nay",
]

IN_SCOPE_QUESTIONS = [
    "RC_OPTIONS bit meanings",
    "hwdef MCU board definition",
    "CRSF CRC polynomial",
    "SERIAL_ORDER pins hwdef ChibiOS",
    "arming check prearm failure causes",
    "AP_Param parameter table implementation",
]


def test_foreign_product_names_get_a_scope_note(con) -> None:
    for text, name in FOREIGN_PRODUCTS:
        payload = query.search(con, text, limit=3)
        joined = " ".join(payload.get("scope_notes") or [])
        assert f"không có {name}" in joined, (text, payload.get("scope_notes"))
        assert payload["confidence"] == "low", text


def test_unknown_version_is_flagged_with_the_pinned_labels(con) -> None:
    labels = [row["version_label"] or row["ref"] for row in
              con.execute("SELECT ref, version_label FROM sources")]
    for text, number in [("tính năng của 5.2", "5.2"),
                         ("ArduPilot 9.9.9 release notes", "9.9.9")]:
        payload = query.search(con, text, limit=3)
        joined = " ".join(payload.get("scope_notes") or [])
        assert number in joined, (text, payload.get("scope_notes"))
        assert "đang ghim" in joined, (text, joined)
        assert any(label in joined for label in labels), (text, joined, labels)


def test_pinned_version_is_not_flagged(con) -> None:
    label = con.execute("SELECT version_label FROM sources WHERE id = 'ardupilot'").fetchone()[0]
    number = re.search(r"\d+\.\d+(?:\.\d+)?", label).group(0)
    payload = query.search(con, f"arming check with firmware {number}", limit=3)
    assert payload["scope_notes"] == [], (number, payload["scope_notes"])


def test_unrelated_topics_get_a_weak_match_note(con) -> None:
    for text in UNRELATED_TOPICS:
        payload = query.search(con, text, limit=3)
        assert "khớp yếu, có thể ngoài kho" in (payload.get("scope_notes") or []), (
            text, payload.get("scope_notes"))
        assert payload["confidence"] == "low", text


def test_in_scope_questions_are_not_flagged(con) -> None:
    for text in IN_SCOPE_QUESTIONS:
        payload = query.search(con, text, limit=5)
        assert payload["found"] is True, text
        assert payload["scope_notes"] == [], (text, payload["scope_notes"])
        assert payload["confidence"] == "high", text


def test_golden_questions_get_no_scope_note(con) -> None:
    golden = yaml.safe_load((REPO / "tests" / "golden.yaml").read_text(encoding="utf-8"))
    for question in golden["questions"]:
        payload = query.search(con, question["q"], scope=question.get("scope", "all"), limit=5)
        assert payload["scope_notes"] == [], (question["id"], question["q"],
                                             payload["scope_notes"])


