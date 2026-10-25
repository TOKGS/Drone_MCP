#!/usr/bin/env python3
"""Generate held-out v3: questions whose answer is UNIQUE, sampled blind.

v2 sampled any heading, but identical headings ("Overview", "Parameters") live in several files,
so a single-target metric is capped by ambiguity rather than by retrieval. v3 keeps only headings
that appear in exactly one indexed document, which makes "which file answers this?" a fair question.

Protocol: fixed seed, generator prints counts and SHA-256 only, never the questions; evaluation runs
with --aggregate-only so the miss list stays unseen.

    python -m research.make_heldout_v3
"""

from __future__ import annotations

import hashlib
import random
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from ardupilot_research_mcp import db  # noqa: E402

SEED = 20261026
COUNT = 30
DOC_SOURCES = ("ardupilot_wiki", "expresslrs_docs", "crsf_spec", "mavlink", "ardupilot")
TEMPLATES_EN = [
    "What do the docs say about {topic}?",
    "Explain {topic}.",
    "Where is {topic} documented?",
    "Summarise the section on {topic}.",
]
TEMPLATES_VI = [
    "Tài liệu nói gì về {topic}?",
    "Giải thích {topic}.",
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

    owners: dict[str, set[tuple[str, str]]] = defaultdict(set)
    for row in rows:
        topic = re.split(r"\s*>\s*", row["heading_path"])[-1].strip()
        if not (6 <= len(topic) <= 60):
            continue
        owners[topic.lower()].add((row["source_id"], row["path"]))

    # Unambiguous only: the heading phrase resolves to exactly one document in the whole index.
    unique = [(topic, next(iter(paths))) for topic, paths in owners.items() if len(paths) == 1]
    if len(unique) < COUNT:
        print(f"only {len(unique)} unambiguous topics; ingest more docs first", file=sys.stderr)
        return 2

    rng = random.Random(SEED)
    picked = rng.sample(unique, COUNT)
    questions = []
    for index, (topic, (source_id, path)) in enumerate(picked, start=1):
        lang = "en" if index % 2 else "vi"
        template = rng.choice(TEMPLATES_EN if lang == "en" else TEMPLATES_VI)
        questions.append({
            "id": f"V3-{index:02d}",
            "lang": lang,
            "q": template.format(topic=topic),
            "expect": [{"source": source_id, "path": path}],
        })

    path_out = REPO / "tests" / "heldout_v3.yaml"
    path_out.write_text(yaml.safe_dump(
        {"version": 3, "generated_by": "research.make_heldout_v3", "seed": SEED,
         "protocol": "unambiguous headings only (each heading owns exactly one file); agent never "
                     "inspects the questions",
         "questions": questions},
        allow_unicode=True, sort_keys=False), encoding="utf-8")
    sha = hashlib.sha256(path_out.read_bytes()).hexdigest()
    (REPO / "docs" / "heldout-v3.sha256").write_text(
        f"{sha}  tests/heldout_v3.yaml\n", encoding="utf-8")

    print(f"written={path_out.name} questions={len(questions)} seed={SEED}")
    print(f"sha256={sha}")
    print(f"unambiguous_topics={len(unique)} "
          f"distribution={dict(Counter(source_id for _, (source_id, _p) in picked))}")
    print("questions intentionally not printed; evaluate with --aggregate-only")
    return 0


if __name__ == "__main__":
    sys.exit(main())
