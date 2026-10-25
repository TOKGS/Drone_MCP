"""Safety rules for dangerous ArduPilot advice.

The product may explain what a parameter does, but must never present disarming safety checks
as a fix. This module classifies a request; `tools/troubleshoot.py` refuses and redirects.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

PROPS_OFF = "Props off for bench tests. SITL before hardware."
CONFIRM_TEMPLATE = "CONFIRM: {action} on {board} with props off."

# Requests whose *intent* is to silence a safety system. `hard` rules are unambiguous even
# inside a question ("is ARMING_CHECK=0 ok?"); `soft` rules are verb-only and lose to an
# explicit informational phrasing ("what does X do").
DANGEROUS = [
    (re.compile(r"arming[_\s]*check\s*=\s*0", re.I), True,
     "sets ARMING_CHECK=0, disabling every pre-arm check"),
    (re.compile(r"arming[_\s]*(skipchk|skip_chk)", re.I), True,
     "changes ARMING_SKIPCHK, which masks specific pre-arm failures"),
    (re.compile(r"skip[_\s-]*mask", re.I), True,
     "uses a skip mask to silence pre-arm checks"),
    (re.compile(r"force[_\s-]*arm", re.I), True,
     "force-arms without the checks completing"),
    (re.compile(r"(skip|mask|bypass)[^.\n]{0,25}(arming|pre-?arm)", re.I), False,
     "skips a pre-arm check"),
    (re.compile(r"arming[^.\n]{0,25}(skip|mask)", re.I), False,
     "masks a pre-arm check"),
    (re.compile(r"(tắt|bỏ qua|bo qua|disable|turn off|deactivate|ignore)[^.\n]{0,25}"
                r"(arming|pre-?arm|failsafe|fence|check)", re.I), False,
     "disables arming, failsafe or fence protection"),
    (re.compile(r"(set|đặt|dat)[^.\n]{0,20}(skip.?mask)[^.\n]{0,20}(0xffff|ffff)", re.I), False,
     "masks every pre-arm check with a full skip mask"),
]

# Questions about a safety parameter are legitimate: they must not be refused.
INFORMATIONAL = re.compile(
    r"^\s*(what|how|why|when|where|which|does|do|is|are|explain|tell me)\b"
    r"|là gì|nghĩa là|giải thích|hoạt động thế nào|dùng để làm gì|có tác dụng gì",
    re.I)

REFUSAL_VI = (
    "Không đưa ra cách tắt/bỏ qua kiểm tra an toàn như một giải pháp. "
    "Hãy sửa nguyên nhân mà pre-arm check báo, hoặc chẩn đoán bằng SITL trước."
)
REFUSAL_EN = (
    "Disabling or masking a pre-arm check is not offered as a fix. "
    "Resolve the cause the check reports, or diagnose in SITL first."
)


@dataclass
class Verdict:
    dangerous: bool
    matches: list[str] = field(default_factory=list)
    why: list[str] = field(default_factory=list)
    informational: bool = False

    def as_dict(self) -> dict:
        return {"dangerous": self.dangerous, "matches": self.matches,
                "why": self.why, "informational": self.informational}


def classify(text: str) -> Verdict:
    """Decide whether a request asks for a safety-disabling workaround."""
    verdict = Verdict(dangerous=False, informational=bool(INFORMATIONAL.search(text or "")))
    hard_hit = False
    for pattern, is_hard, reason in DANGEROUS:
        match = pattern.search(text or "")
        if not match:
            continue
        verdict.matches.append(match.group(0))
        verdict.why.append(reason)
        hard_hit = hard_hit or is_hard
    # A pure question ("what does ARMING_CHECK do") stays informational unless a hard rule fires.
    verdict.dangerous = bool(verdict.matches) and (hard_hit or not verdict.informational)
    return verdict


def safety_block(action: str = "<action>", board: str = "<board>") -> dict:
    return {"props_off": PROPS_OFF, "confirm": CONFIRM_TEMPLATE.format(action=action, board=board)}


def refusal_payload(verdict: Verdict, *, lang: str = "vi") -> dict:
    return {
        "found": True,
        "dangerous": True,
        "refused_as_fix": True,
        "language": lang,
        "matches": verdict.matches,
        "why_dangerous": verdict.why,
        "message": REFUSAL_VI if lang == "vi" else REFUSAL_EN,
        "message_en": REFUSAL_EN,
        "safe_path": [
            "read the actual pre-arm failure text and fix that cause",
            "reproduce in SITL before touching hardware",
            "for a real bench test: props off, vehicle restrained, and a CONFIRM line in the log",
        ],
        "safety": safety_block(),
        "note": "It is fine to ask what a safety parameter does; this refusal only covers using "
                "it to bypass a check.",
    }
