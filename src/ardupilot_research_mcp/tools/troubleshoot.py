"""troubleshoot: evidence-backed triage with a hard safety gate and no invented steps."""

from __future__ import annotations

import sqlite3

from .. import query as retrieval, safety
from ._base import guarded

MAX_EVIDENCE = 6


@guarded
def troubleshoot(con: sqlite3.Connection, symptom: str, context: str | None = None) -> dict:
    """Triage an ArduPilot symptom using only the indexed corpus, with explicit safety rules.

    Returns the source-backed evidence for the symptom (each item a citation with cite_id) plus
    the mandatory bench-test safety block. It never invents a fix: the steps live in the cited
    documents, and hardware procedures always carry "Props off for bench tests. SITL before
    hardware." Requests that use a safety bypass as the fix (ARMING_CHECK=0, ARMSKIPCHK, force
    arm, disabled failsafe/fence) are refused and redirected to the real cause. Questions about
    what such a parameter *does* are answered normally.
    """
    text = (symptom or "").strip()
    if not text:
        return {"found": False, "error": "empty symptom", "safety": safety.safety_block()}

    verdict = safety.classify(text)
    dangerous_context = safety.classify(context or "") if context else None
    if verdict.dangerous or (dangerous_context and dangerous_context.dangerous):
        effective = verdict if verdict.dangerous else dangerous_context
        refusal = safety.refusal_payload(effective, lang="vi")
        refusal["citations"] = retrieval.search(
            con, "pre-arm check failure arming check", scope="docs", limit=3)["results"]
        return refusal

    searches = [retrieval.search(con, text, scope="docs", limit=MAX_EVIDENCE),
                retrieval.search(con, text, scope="code", limit=3)]
    evidence: list[dict] = []
    seen: set[str] = set()
    for payload in searches:
        for item in payload.get("results", []):
            if item["cite_id"] in seen:
                continue
            seen.add(item["cite_id"])
            evidence.append(item)

    tiers = {item["tier"] for item in evidence}
    confidence = ("high" if "T1" in tiers and len(evidence) >= 4
                  else "medium" if len(evidence) >= 2 else "low")

    return {
        "found": bool(evidence),
        "symptom": text,
        "language": "vi" if any(word in text.lower() for word in ("không", "lỗi", "bị", "tại sao"))
                    else "en",
        "confidence": confidence,
        "evidence": evidence,
        "citations": [item["cite_id"] for item in evidence],
        "safety": safety.safety_block("<the procedure you apply>", "<your board>"),
        "symptom_evidence_only": False,
        "note": ("Evidence is ordered by retrieval score, not by a diagnostic script: read the "
                 "cited lines before acting. Nothing in this corpus is a forum post, so every "
                 "item is source or documentation evidence, not community anecdote."
                 if evidence else
                 "No indexed source matches this symptom; nothing was invented. Try a shorter "
                 "phrase or the English term (packet loss, arming failure, vibration)."),
    }
