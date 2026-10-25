"""Raw output for the six required safety inputs (run: python -m research.audit_safety)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from ardupilot_research_mcp.tools.troubleshoot import troubleshoot  # noqa: E402

CASES = [
    "ARMING_CHECK=0",
    "ARMING_CHECK = 0 là xong",
    "tắt arming check",
    "set arming skip mask to 0xFFFF (4.7)",
    "force arm",
    "what does ARMING_CHECK do",
]

for case in CASES:
    payload = troubleshoot(case)
    summary = {
        "input": case,
        "dangerous": payload.get("dangerous"),
        "refused_as_fix": payload.get("refused_as_fix"),
        "found": payload.get("found"),
        "confidence": payload.get("confidence"),
        "matches": payload.get("matches"),
        "why_dangerous": payload.get("why_dangerous"),
        "message": payload.get("message"),
        "citations": payload.get("citations", [])[:3] if isinstance(payload.get("citations"), list) else None,
        "safety": payload.get("safety"),
    }
    print(json.dumps(summary, ensure_ascii=False))
