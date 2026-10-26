#!/usr/bin/env python3
"""Validate an eval-set fragment or a merged set, printing counts and error ids only.

    python -m research.validate_eval_set --set docs/upgrade/scratch/q_b1.yaml
    python -m research.validate_eval_set --set tests/eval_v4_dev.yaml --strict-v4

Never prints the question text: a fragment author gets `id` plus an error code and a short detail
(a path, a count, a token count), which is enough to fix the entry without echoing the question.

Checks
  1. schema: `questions` is a non-empty list; unique non-empty ids; `lang` in {vi,en,mixed};
     `category` known when present (`--strict-v4` requires it); `expect_none` implies
     `category: negative` and no `expect`.
  2. ground truth exists: every `expect.path` matches at least one row in `documents` for that
     `source` (needs the built index; the check is reported as skipped otherwise).
  3. `answer_snippet` is at least 12 characters and occurs verbatim in a chunk of a matching
     document.
  4. no duplicate questions after folding case, diacritics and punctuation; no question is a
     substring of another.
  5. an `expect_none` question is rejected when three or more of its content words each appear in
     three or more indexed documents, i.e. the corpus does answer it.
"""

from __future__ import annotations

import argparse
import re
import sys
import unicodedata
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from ardupilot_research_mcp import config, query  # noqa: E402

CATEGORIES = {"param", "code", "protocol", "hwdef", "wiki", "elrs_edgetx", "troubleshoot",
              "negative"}
LANGS = {"vi", "en", "mixed"}
MIN_SNIPPET = 12
NEGATIVE_MIN_WORDS = 3
NEGATIVE_DOC_FLOOR = 3


def fold(text: str) -> str:
    """Lowercase and strip diacritics, so 'tốc độ' and 'toc do' compare equal."""
    decomposed = unicodedata.normalize("NFKD", text or "")
    stripped = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return stripped.lower()


def normalise(text: str) -> str:
    return " ".join(re.findall(r"[a-z0-9_]+", fold(text)))


def content_words(question: dict) -> list[str]:
    """ASCII content words the retriever could match; Vietnamese diacritics fold to ASCII."""
    words = re.findall(r"[a-z][a-z0-9_]+", normalise(question.get("q", "")))
    return [word for word in words if len(word) > 3 and word not in query.STOPWORDS]


def targets(question: dict) -> list[dict]:
    if "expect" in question:
        return question["expect"] or []
    if "expect_source" in question:
        return [{"source": question["expect_source"],
                 "path": question.get("expect_path_contains") or "."}]
    if "source" in question:
        return [{"source": question["source"], "path": question.get("path") or "."}]
    return []


def _error(question: dict, code: str, detail: str = "") -> dict:
    return {"id": question.get("id") or "(no id)", "code": code, "detail": detail}


def _documents_match(con, source: str, path: str) -> bool:
    if path == ".":
        return bool(con.execute("SELECT 1 FROM documents WHERE source_id=? LIMIT 1",
                                (source,)).fetchone())
    return bool(con.execute("SELECT 1 FROM documents WHERE source_id=? AND path LIKE ? LIMIT 1",
                            (source, f"%{path}%")).fetchone())


def _snippet_found(con, question: dict, snippet: str) -> bool:
    for target in targets(question):
        path = target.get("path") or "."
        sql = ("SELECT 1 FROM chunks c JOIN documents d ON d.id = c.document_id"
               " WHERE d.source_id=? AND INSTR(c.text, ?) > 0")
        args: list[object] = [target.get("source"), snippet]
        if path != ".":
            sql += " AND d.path LIKE ?"
            args.append(f"%{path}%")
        if con.execute(sql + " LIMIT 1", args).fetchone():
            return True
    return False


def validate(questions: list[dict], con=None, *, strict_v4: bool = False) -> dict:
    """Return counts plus the error list; `con` may be None (document checks are then skipped)."""
    errors: list[dict] = []
    checks = {"schema": 0, "documents": 0, "snippets": 0, "duplicates": 0, "negatives": 0}
    seen_ids: dict[str, str] = {}
    seen_questions: list[tuple[str, str]] = []
    categories: dict[str, int] = {}
    langs: dict[str, int] = {}
    documents_checked = con is not None

    for question in questions:
        if not isinstance(question, dict):
            errors.append(_error({}, "not_a_mapping"))
            continue
        question_id = question.get("id")
        if not isinstance(question_id, str) or not question_id.strip():
            errors.append(_error(question, "missing_id"))
        elif question_id in seen_ids:
            errors.append(_error(question, "duplicate_id", question_id))
        else:
            seen_ids[question_id] = question_id

        lang = question.get("lang")
        if lang not in LANGS:
            errors.append(_error(question, "bad_lang", str(lang)))
            checks["schema"] += 1
        else:
            langs[lang] = langs.get(lang, 0) + 1

        category = question.get("category")
        if category is None:
            if strict_v4:
                errors.append(_error(question, "missing_category"))
        elif category not in CATEGORIES:
            errors.append(_error(question, "bad_category", str(category)))
        else:
            categories[category] = categories.get(category, 0) + 1

        if not isinstance(question.get("q"), str) or len(question["q"].strip()) < 4:
            errors.append(_error(question, "missing_question"))
            continue

        snippet = question.get("answer_snippet")
        if snippet is not None:
            if len(snippet) < MIN_SNIPPET:
                errors.append(_error(question, "snippet_too_short", str(len(snippet))))
            elif con is not None and not _snippet_found(con, question, snippet):
                errors.append(_error(question, "snippet_not_in_corpus"))

        if question.get("expect_none"):
            checks["negatives"] += 1
            if category != "negative":
                errors.append(_error(question, "negative_without_category"))
            if targets(question):
                errors.append(_error(question, "negative_has_expect"))
            answerable = [word for word in content_words(question)
                          if con is not None
                          and query._document_frequency(con, word, NEGATIVE_DOC_FLOOR)
                          >= NEGATIVE_DOC_FLOOR]
            if len(answerable) >= NEGATIVE_MIN_WORDS:
                errors.append(_error(question, "negative_is_answerable",
                                     f"{len(answerable)} words in corpus"))
        else:
            question_targets = targets(question)
            if not question_targets:
                errors.append(_error(question, "missing_expect"))
            known_sources = set(config.source_by_id()) if con is None else {
                row[0] for row in con.execute("SELECT id FROM sources")}
            for target in question_targets:
                checks["documents"] += 1
                source = target.get("source")
                if source not in known_sources:
                    errors.append(_error(question, "unknown_source", str(source)))
                    continue
                if con is not None and not _documents_match(con, source, target.get("path") or "."):
                    errors.append(_error(question, "path_not_found",
                                         f"{source}:{target.get('path')}"))
            if snippet is not None:
                checks["snippets"] += 1

    # duplicates, after folding case/diacritics/punctuation
    for index, question in enumerate(questions):
        if not isinstance(question, dict):
            continue
        normal = normalise(question.get("q", ""))
        for other_normal, other_id in seen_questions:
            if normal and normal == other_normal:
                errors.append(_error(question, "duplicate_question", other_id))
            elif normal and other_normal and (
                    normal in other_normal or other_normal in normal):
                errors.append(_error(question, "question_substring", other_id))
        seen_questions.append((normal, question.get("id")))
    checks["duplicates"] = len([error for error in errors
                                if error["code"] in ("duplicate_question", "question_substring")])

    return {"questions": len(questions), "categories": categories, "langs": langs,
            "checks": checks, "errors": errors, "documents_checked": documents_checked}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--set", required=True)
    parser.add_argument("--strict-v4", action="store_true",
                        help="require `category` on every question (the v4 rule)")
    args = parser.parse_args(argv)

    payload = yaml.safe_load(Path(args.set).read_text(encoding="utf-8"))
    questions = payload.get("questions") if isinstance(payload, dict) else payload
    if not isinstance(questions, list) or not questions:
        print(f"set={Path(args.set).name} questions=0")
        print("  - id=(none) code=no_questions")
        return 1

    con = None
    if config.index_exists():
        from ardupilot_research_mcp import db

        con = db.connect()
        if not con.execute("SELECT COUNT(*) FROM documents").fetchone()[0]:
            con = None
    report = validate(questions, con, strict_v4=args.strict_v4)

    print(f"set={Path(args.set).name} questions={report['questions']}"
          f" db={'checked' if report['documents_checked'] else 'skipped (no index)'}")
    print("categories: " + " ".join(f"{name}={count}"
                                    for name, count in sorted(report["categories"].items())))
    print("langs: " + " ".join(f"{name}={count}"
                               for name, count in sorted(report["langs"].items())))
    print(f"snippets={report['checks']['snippets']} negatives={report['checks']['negatives']}")
    print(f"errors: {len(report['errors'])}")
    for error in report["errors"]:
        detail = f" {error['detail']}" if error["detail"] else ""
        print(f"  - id={error['id']} code={error['code']}{detail}")
    return 0 if not report["errors"] else 1


if __name__ == "__main__":
    sys.exit(main())
