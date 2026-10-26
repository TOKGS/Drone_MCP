#!/usr/bin/env python3
"""Retrieval metrics over a question set.

    python -m research.eval_retrieval --set tests/golden.yaml [--k 5] [--verbose]
    python -m research.eval_retrieval --set tests/heldout_v3.yaml --aggregate-only
    python -m research.eval_retrieval --set tests/eval_v4_heldout.yaml --aggregate-only \\
        --json docs/upgrade/runs/heldout.json
    python -m research.eval_retrieval --compare docs/upgrade/baseline/heldout.json new.json

Scoring rule per question, unchanged since v1: a result is a hit when its source matches `source`
and its path contains `path`. recall@k = at least one hit in the top k; precision@1 = the first
result is a hit; MRR = 1 / rank of the first hit.

Additive fields a set may use (all optional, old sets keep working):

  category        one of CATEGORIES; rows are also reported per category
  answer_snippet  a verbatim substring (>= MIN_SNIPPET chars); chunk-hit@k requires a top-k hit
                  whose excerpt contains it, so "right file, wrong paragraph" is visible
  expect_none     the question is deliberately out of scope; it passes when the payload is
                  `found:false` or has no results, and it is excluded from recall / P@1 / MRR

Every run also splits the aggregate by whether the question text itself carries Vietnamese
diacritics (`script: ascii-only | diacritics`, computed from `q`, not from a declared field) and by
`lang` (`vi | mixed | en`). Both tables report the sample size `n`, because a group with a handful
of questions moves in large steps.

A set whose SHA-256 is recorded in a `docs/*.sha256` file (the sha256sum layout, repo-relative
path) is verified before any question runs; `--verify-sha` forces a specific file. A mismatch exits
non-zero and prints no question text.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import unicodedata
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from ardupilot_research_mcp import db, query  # noqa: E402

CATEGORIES = ("param", "code", "protocol", "hwdef", "wiki", "elrs_edgetx", "troubleshoot",
              "negative")
LANGS = ("vi", "en", "mixed")
MIN_SNIPPET = 12
RECALL_FLOOR = 0.8
SCRIPT_ASCII = "ascii-only"
SCRIPT_DIACRITICS = "diacritics"


def has_diacritics(text: str) -> bool:
    """True when the text carries a Vietnamese mark (including the letter d with a stroke)."""
    decomposed = unicodedata.normalize("NFD", text or "")
    return any(unicodedata.combining(ch) for ch in decomposed) or any(ch in "đĐ" for ch in text)


def question_script(question: dict) -> str:
    """`ascii-only` or `diacritics`, read from the question text, not from a declared flag."""
    return SCRIPT_DIACRITICS if has_diacritics(str(question.get("q") or "")) else SCRIPT_ASCII


class HashMismatch(RuntimeError):
    """The set on disk is not the set that was frozen."""


# ------------------------------------------------------------------ set identity
def _repo_rel(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO).as_posix()
    except ValueError:
        return path.name


def set_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def find_sha_line(set_path: Path) -> tuple[Path, str, str] | None:
    """The first `docs/*.sha256` line that names this set: (file, digest, repo-relative path)."""
    rel = _repo_rel(set_path)
    for sha_file in sorted((REPO / "docs").glob("*.sha256")):
        for line in sha_file.read_text(encoding="utf-8").splitlines():
            parts = line.split()
            if len(parts) < 2:
                continue
            if Path(parts[1]).as_posix() == rel:
                return sha_file, parts[0], parts[1]
    return None


def verify_hash(set_path: Path, sha_file: Path | None = None) -> dict:
    """Verify the set against its frozen digest; raise HashMismatch when it changed."""
    if sha_file is not None:
        parts = (sha_file.read_text(encoding="utf-8").splitlines() or [""])[0].split()
        if len(parts) < 2:
            raise HashMismatch(f"{sha_file.name}: no '<sha>  <path>' line")
        found_file, expected, rel = sha_file, parts[0], parts[1]
    else:
        found = find_sha_line(set_path)
        if found is None:
            return {"verified": False, "sha256": set_digest(set_path), "sha_file": None}
        found_file, expected, rel = found
    actual = set_digest(set_path)
    if actual != expected:
        raise HashMismatch(f"{rel}: sha256 {actual} but {found_file.name} records {expected}")
    return {"verified": True, "sha256": actual, "sha_file": found_file.name}


# ------------------------------------------------------------------ scoring
def expectations(question: dict) -> list[dict]:
    """Accept every set format in the repo without touching the frozen files.

    * v1 (held-out):  expect_source + expect_path_contains
    * v2 (golden):    expect: [{source, path}, ...]
    * v0 fallback:    source + path
    """
    if "expect" in question:
        return question["expect"]
    if "expect_source" in question:
        return [{"source": question["expect_source"],
                 "path": question.get("expect_path_contains") or "."}]
    return [{"source": question["source"], "path": question.get("path") or "."}]


def is_hit(result: dict, question: dict) -> bool:
    for target in expectations(question):
        if result.get("source_id") != target["source"]:
            continue
        path = target.get("path") or "."
        if path == "." or path in result.get("path", ""):
            return True
    return False


def _snippet(question: dict) -> str | None:
    snippet = question.get("answer_snippet")
    if not snippet:
        return None
    if len(snippet) < MIN_SNIPPET:
        raise ValueError(f"{question.get('id')}: answer_snippet is shorter than {MIN_SNIPPET}")
    return snippet


def score_question(question: dict, results: list[dict], k: int) -> dict:
    """One record per question; negatives never count towards recall / P@1 / MRR."""
    snippet = _snippet(question)
    record = {
        "id": question.get("id"),
        "lang": question.get("lang", "en"),
        "script": question_script(question),
        "category": question.get("category"),
        "scope": question.get("scope", "all"),
        "has_snippet": snippet is not None,
        "negative": bool(question.get("expect_none")),
        "rank": None,
        "hit": False,
        "chunk_hit": False,
        "negative_pass": False,
        "top_path": results[0].get("path") if results else None,
    }
    if record["negative"]:
        record["negative_pass"] = not results
        return record
    first_hit = next((rank for rank, item in enumerate(results, start=1) if is_hit(item, question)),
                     None)
    record["rank"] = first_hit
    record["hit"] = bool(first_hit and first_hit <= k)
    if snippet is not None:
        record["chunk_hit"] = any(
            is_hit(item, question) and snippet in (item.get("excerpt") or "")
            for item in results[:k])
    return record


def evaluate(questions: list[dict], search, k: int) -> list[dict]:
    """Score every question with `search(question) -> payload`; no printing, no I/O."""
    records = []
    for question in questions:
        payload = search(question) or {}
        records.append(score_question(question, payload.get("results") or [], k))
    return records


def _summarise(records: list[dict]) -> dict:
    positives = [record for record in records if not record["negative"]]
    negatives = [record for record in records if record["negative"]]
    with_snippet = [record for record in positives if record["has_snippet"]]
    reciprocal = sum(1.0 / record["rank"] for record in positives if record["rank"])
    summary = {
        "questions": len(records),
        "positives": len(positives),
        "negatives": len(negatives),
        "recall_at_k": (sum(record["hit"] for record in positives) / len(positives)
                        if positives else None),
        "precision_at_1": (sum(record["rank"] == 1 for record in positives) / len(positives)
                           if positives else None),
        "mrr": (reciprocal / len(positives)) if positives else None,
        "chunk_hit": (sum(record["chunk_hit"] for record in with_snippet) / len(with_snippet)
                      if with_snippet else None),
        "negative_pass": (sum(record["negative_pass"] for record in negatives) / len(negatives)
                          if negatives else None),
        "hits": sum(record["hit"] for record in positives),
        "precision_1_count": sum(record["rank"] == 1 for record in positives),
    }
    return summary


def aggregate(records: list[dict]) -> dict:
    """Overall plus one row per category, per language and per question script."""
    def group(key: str) -> dict[str, dict]:
        buckets: dict[str, list[dict]] = {}
        for record in records:
            value = record.get(key) or "-"
            buckets.setdefault(value, []).append(record)
        return {name: _summarise(rows) for name, rows in sorted(buckets.items())}

    return {"overall": _summarise(records), "per_category": group("category"),
            "per_lang": group("lang"), "per_script": group("script")}


# ------------------------------------------------------------------ printing
def _ratio(value: float | None) -> str:
    return "-" if value is None else f"{value:.3f}"


def print_table(title: str, rows: dict[str, dict]) -> None:
    if not rows:
        return
    print(f"\n{title}")
    print(f"{'group':<14}{'n':>4}{'recall@5':>10}{'P@1':>8}{'MRR':>8}"
          f"{'chunk-hit':>11}{'neg-pass':>10}")
    for name, summary in rows.items():
        print(f"{name:<14}{summary['questions']:>4}{_ratio(summary['recall_at_k']):>10}"
              f"{_ratio(summary['precision_at_1']):>8}{_ratio(summary['mrr']):>8}"
              f"{_ratio(summary['chunk_hit']):>11}{_ratio(summary['negative_pass']):>10}")


def payload_json(set_path: Path, sha: dict, k: int, records: list[dict],
                 summary: dict, aggregate_only: bool) -> dict:
    rows = []
    for record in records:
        row = {key: record[key] for key in ("id", "lang", "script", "category", "scope", "rank",
                                            "hit", "chunk_hit", "negative", "negative_pass",
                                            "top_path")}
        rows.append(row)
    return {
        "set": set_path.name,
        "sha256": sha.get("sha256"),
        "sha_verified": bool(sha.get("verified")),
        "k": k,
        "questions": summary["overall"]["questions"],
        "positives": summary["overall"]["positives"],
        "negatives": summary["overall"]["negatives"],
        "overall": summary["overall"],
        "per_category": summary["per_category"],
        "per_lang": summary["per_lang"],
        "per_script": summary["per_script"],
        "rows": rows if not aggregate_only else None,
    }


def compare(base: dict, new: dict) -> int:
    """Per-category delta table; a negative delta on recall@k or MRR is flagged."""
    print(f"comparison: {base.get('set')} -> {new.get('set')}  k={new.get('k')}")
    print(f"{'group':<14}{'metric':<12}{'base':>8}{'new':>8}{'delta':>9}  flag")
    flagged = 0

    def row(group: str, metric: str, before: float | None, after: float | None) -> None:
        nonlocal flagged
        if before is None or after is None:
            print(f"{group:<14}{metric:<12}{_ratio(before):>8}{_ratio(after):>8}{'-':>9}  -")
            return
        delta = after - before
        flag = "DROP" if delta < 0 else ""
        if flag:
            flagged += 1
        print(f"{group:<14}{metric:<12}{before:>8.3f}{after:>8.3f}{delta:>+9.3f}  {flag}")

    for metric in ("recall_at_k", "mrr"):
        row("overall", metric, base["overall"].get(metric), new["overall"].get(metric))
    groups = sorted(set(base.get("per_category") or {}) | set(new.get("per_category") or {}))
    for group in groups:
        before = (base.get("per_category") or {}).get(group) or {}
        after = (new.get("per_category") or {}).get(group) or {}
        for metric in ("recall_at_k", "mrr"):
            row(group, metric, before.get(metric), after.get(metric))
    print(f"\nflagged drops: {flagged}")
    return 0


# ------------------------------------------------------------------ CLI
def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--set", default=str(REPO / "tests" / "golden.yaml"))
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument("--aggregate-only", action="store_true",
                        help="print metrics only (used for the blind held-out set)")
    parser.add_argument("--verify-sha", default=None,
                        help="sha256sum-style file to verify the set against")
    parser.add_argument("--json", default=None, help="write machine-readable results here")
    parser.add_argument("--compare", nargs=2, metavar=("BASE", "NEW"),
                        help="print a per-category delta table for two --json files")
    parser.add_argument("--no-floor", action="store_true",
                        help="do not exit 1 when recall@k is under 0.8 (for a baseline that is "
                             "not tuned yet; the v4 sets are measured, not gated, on that floor)")
    args = parser.parse_args(argv)

    if args.compare:
        base = json.loads(Path(args.compare[0]).read_text(encoding="utf-8"))
        new = json.loads(Path(args.compare[1]).read_text(encoding="utf-8"))
        return compare(base, new)

    set_path = Path(args.set)
    try:
        sha = verify_hash(set_path, Path(args.verify_sha) if args.verify_sha else None)
    except HashMismatch as exc:
        print(f"sha256 mismatch: {exc}", file=sys.stderr)
        return 2

    data = yaml.safe_load(set_path.read_text(encoding="utf-8"))
    questions = data["questions"]
    for question in questions:
        category = question.get("category")
        if category is not None and category not in CATEGORIES:
            print(f"unknown category {category!r} on {question.get('id')}", file=sys.stderr)
            return 2
        if question.get("lang") not in (None, *LANGS):
            print(f"unknown lang {question.get('lang')!r} on {question.get('id')}", file=sys.stderr)
            return 2

    con = db.connect()

    def search(question: dict) -> dict:
        return query.search(con, question["q"], scope=question.get("scope", "all"),
                            limit=max(args.k, 5))

    records = evaluate(questions, search, args.k)
    summary = aggregate(records)
    overall = summary["overall"]

    print(f"set={set_path.name} questions={overall['questions']} k={args.k}")
    if sha["verified"]:
        print(f"sha256: verified against {sha['sha_file']} ({sha['sha256'][:16]}...)")
    if overall["positives"]:
        print(f"recall@{args.k} = {overall['hits']}/{overall['positives']} = "
              f"{overall['recall_at_k']:.3f}")
        print(f"precision@1 = {overall['precision_1_count']}/{overall['positives']} = "
              f"{overall['precision_at_1']:.3f}")
        print(f"MRR = {overall['mrr']:.3f}")
    if overall["chunk_hit"] is not None:
        print(f"chunk-hit@{args.k} = {_ratio(overall['chunk_hit'])}")
    if overall["negative_pass"] is not None:
        print(f"negative-pass = {_ratio(overall['negative_pass'])}")

    if any(question.get("category") for question in questions):
        print_table("per category", summary["per_category"])
    if len(summary["per_lang"]) > 1 or "-" not in summary["per_lang"]:
        print_table("per language", summary["per_lang"])
    print_table("per script (read from the question text)", summary["per_script"])

    if args.verbose and not args.aggregate_only:
        print()
        for record in records:
            note = (f"NEG {'PASS' if record['negative_pass'] else 'FAIL'}"
                    if record["negative"] else
                    f"{'HIT' if record['hit'] else 'MISS'} rank={record['rank']}"
                    f" top={record['top_path'] or '(none)'}")
            print(f"  {record['id']:<8}{record['lang']:<6}{note}")

    if args.json:
        Path(args.json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json).write_text(json.dumps(
            payload_json(set_path, sha, args.k, records, summary, args.aggregate_only),
            ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"\nwrote {args.json}")

    if not args.aggregate_only:
        misses = [record for record in records if not record["hit"] and not record["negative"]]
        failed_negatives = [record for record in records
                            if record["negative"] and not record["negative_pass"]]
        if misses or failed_negatives:
            print(f"\nmisses ({len(misses) + len(failed_negatives)}):")
            for record in misses:
                expected = " | ".join(f"{target['source']}:{target.get('path', '.')}"
                                      for target in expectations(
                                          next(q for q in questions if q.get("id") == record["id"])))
                print(f"  - {record['id']} ({record['lang']}) expected {expected} "
                      f"top={record['top_path'] or '(none)'} rank={record['rank']}")
            for record in failed_negatives:
                print(f"  - {record['id']} ({record['lang']}) expected found:false "
                      f"top={record['top_path']}")

    if args.no_floor:
        return 0
    if overall["positives"] and overall["recall_at_k"] < RECALL_FLOOR:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
