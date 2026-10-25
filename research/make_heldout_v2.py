#!/usr/bin/env python3
"""Generate a NEW held-out set mechanically, so the implementer never sees the questions.

Protocol (state it in the report):
  * questions are sampled from indexed document headings by a fixed seed — no manual curation,
    no inspection of the produced file by the agent;
  * the expected target for a question is the file that owns that heading;
  * the generator prints only counts, distribution and the SHA-256, never the questions;
  * evaluation runs with `--aggregate-only`, so the agent cannot read the miss list either.

This measures "given a heading phrase, can retrieval find the owning file?" — a weaker but
honest and blind benchmark, not a substitute for human-written semantic questions.

    python -m research.make_heldout_v2
"""

from __future__ import annotations

import hashlib
import random
import re
import sys
from collections import Counter
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from ardupilot_research_mcp import config, db  # noqa: E402

SEED = 20261025
COUNT = 30
DOC_SOURCES = ("ardupilot_wiki", "expresslrs_docs", "crsf_spec", "mavlink")
TEMPLATES_EN = [
    "What do the docs say about {topic}?",
    "Explain {topic} in ArduPilot.",
    "Where is {topic} documented?",
]
TEMPLATES_VI = [
    "Tài liệu nói gì về {topic}?",
    "Giải thích {topic} trong ArduPilot.",
    "{topic} được mô tả ở đâu?",
]


def main() -> int:
    con = db.connect()
    rows = con.execute(
        "SELECT DISTINCT c.heading_path, d.source_id, d.path FROM chunks c"
        " JOIN documents d ON d.id = c.document_id"
        f" WHERE d.source_id IN ({','.join('?' * len(DOC_SOURCES))})"
        "   AND c.heading_path IS NOT NULL AND LENGTH(c.heading_path) > 12",
        DOC_SOURCES).fetchall()
    candidates = []
    for row in rows:
        heading = row["heading_path"]
        topic = re.split(r"\s*>\s*", heading)[-1].strip()
        if not topic or len(topic) < 6 or len(topic) > 60:
            continue
        candidates.append({"topic": topic, "source": row["source_id"], "path": row["path"]})
    if len(candidates) < COUNT:
        print(f"only {len(candidates)} candidates; ingest more docs first", file=sys.stderr)
        return 2

    rng = random.Random(SEED)
    picked = rng.sample(candidates, COUNT)
    questions = []
    for index, item in enumerate(picked, start=1):
        lang = "en" if index % 2 else "vi"
        template = rng.choice(TEMPLATES_EN if lang == "en" else TEMPLATES_VI)
        questions.append({
            "id": f"V2-{index:02d}",
            "lang": lang,
            "q": template.format(topic=item["topic"]),
            "expect": [{"source": item["source"], "path": item["path"]}],
        })
    document = {
        "version": 2,
        "generated_by": "research.make_heldout_v2",
        "seed": SEED,
        "protocol": "mechanical sample of indexed headings; agent never inspects questions",
        "questions": questions,
    }

    path = REPO / "tests" / "heldout_v2.yaml"
    text = yaml.safe_dump(document, allow_unicode=True, sort_keys=False)
    path.write_text(text, encoding="utf-8")
    sha = hashlib.sha256(path.read_bytes()).hexdigest()
    (REPO / "docs" / "heldout-v2.sha256").write_text(
        f"{sha}  tests/heldout_v2.yaml\n", encoding="utf-8")

    distribution = Counter(item["source"] for item in picked)
    print(f"written={path.name} questions={len(questions)} seed={SEED}")
    print(f"sha256={sha}")
    print(f"distribution={dict(distribution)}")
    print("questions intentionally not printed; evaluate with --aggregate-only")
    return 0


if __name__ == "__main__":
    sys.exit(main())
