"""troubleshoot: evidence-backed triage with a hard safety gate and no invented steps."""

from __future__ import annotations

import sqlite3

from .. import query as retrieval, safety
from ._base import guarded

MAX_EVIDENCE = 6


@guarded
def troubleshoot(con: sqlite3.Connection, symptom: str, context: str | None = None) -> dict:
    """Triage an ArduPilot symptom using only the indexed corpus, with explicit safety rules.

    Returns the source-backed evidence for the symptom (each item a citation with cite_id). It
    never invents a fix: the steps live in the cited documents. Requests that use a safety bypass
    as the fix (disabling/masking an arming, pre-arm, failsafe or fence check, force arm, or
    zeroing a safety parameter - Vietnamese or English) are refused, and the refusal cites why
    the check exists, never the disabling step. Questions about what such a parameter does are
    answered normally. The bench-test props-off line is attached when the gate fires or the answer
    describes a hardware procedure, not to pure informational answers.
    """
    text = (symptom or "").strip()
    if not text:
        return {"found": False, "error": "empty symptom",
                "safety": safety.safety_block(include_props_off=False)}

    verdict = safety.classify(text)
    dangerous_context = safety.classify(context or "") if context else None
    if verdict.dangerous or (dangerous_context and dangerous_context.dangerous):
        effective = verdict if verdict.dangerous else dangerous_context
        refusal = safety.refusal_payload(effective, lang="vi")
        # Cite why the check exists, never the disabling recipe: the gate must not hand back
        # the very step it refuses. If every candidate excerpt also quotes a turn-off step,
        # return none and say so instead of relaxing the filter.
        citations = safety.safe_citations(
            retrieval.search(con, "pre-arm safety checks prevent crashes fly-aways",
                             scope="docs", limit=8)["results"])
        refusal["citations"] = citations
        if not citations:
            refusal["citations_note"] = (
                "No indexed excerpt explains the purpose of the check without also quoting a "
                "disabling step, so no citation is returned.")
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
        "safety_branch": verdict.branch,
        "language": "vi" if any(word in text.lower() for word in ("không", "lỗi", "bị", "tại sao"))
                    else "en",
        "confidence": confidence,
        "evidence": evidence,
        "citations": [item["cite_id"] for item in evidence],
        "safety": safety.safety_block("<the procedure you apply>", "<your board>",
                                      include_props_off=safety.hardware_procedure(text)),
        "symptom_evidence_only": False,
        "note": ("Evidence is ordered by retrieval score, not by a diagnostic script: read the "
                 "cited lines before acting. Nothing in this corpus is a forum post, so every "
                 "item is source or documentation evidence, not community anecdote."
                 if evidence else
                 "No indexed source matches this symptom; nothing was invented. Try a shorter "
                 "phrase or the English term (packet loss, arming failure, vibration)."),
    }
