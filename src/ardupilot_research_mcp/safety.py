"""Safety rules for dangerous ArduPilot advice.

The product may explain what a parameter does, but must never present disarming safety checks
as a fix. `tools/troubleshoot.py` refuses and redirects.

Classification is data-driven (`safety_rules.yaml`), not a list of ad-hoc regexes: a request is a
bypass when a disable verb targets a safety object, or when a safety parameter/limit is zeroed.
Phrases are matched on folded text (lowercase, diacritics stripped, punctuation as boundary), so
Vietnamese with diacritics, Vietnamese without them, and English hit the same rule.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import yaml

PROPS_OFF = "Props off for bench tests. SITL before hardware."
CONFIRM_TEMPLATE = "CONFIRM: {action} on {board} with props off."

RULES_PATH = Path(__file__).with_name("safety_rules.yaml")

# How many tokens may separate a turn-off verb from a safety object in a citation excerpt before
# the sentence stops being "the disabling recipe".
EXCERPT_WINDOW = 8

REFUSAL_VI = (
    "Không đưa ra cách tắt/bỏ qua kiểm tra an toàn như một giải pháp. "
    "Hãy sửa nguyên nhân mà pre-arm check báo, hoặc chẩn đoán bằng SITL trước."
)
REFUSAL_EN = (
    "Disabling or masking a pre-arm check is not offered as a fix. "
    "Resolve the cause the check reports, or diagnose in SITL first."
)
SAFE_PATH = [
    "read the actual pre-arm failure text and fix that cause",
    "reproduce in SITL before touching hardware",
    "for a real bench test: props off, vehicle restrained, and a CONFIRM line in the log",
]


@dataclass(frozen=True)
class _Rules:
    verbs: tuple[tuple[str, str], ...]
    objects: tuple[tuple[str, str], ...]
    info: tuple[tuple[str, str], ...]
    hardware: tuple[tuple[str, str], ...]
    check_words: tuple[tuple[str, str], ...]
    purpose: tuple[tuple[str, str], ...]
    params: tuple[re.Pattern[str], ...]
    values: tuple[re.Pattern[str], ...]
    excerpts: tuple[re.Pattern[str], ...]


def fold(text: str) -> str:
    """Lowercase and strip diacritics, so 'tắt', 'tat' and 'TẮT' are one form."""
    lowered = unicodedata.normalize("NFD", (text or "").lower())
    stripped = "".join(ch for ch in lowered if not unicodedata.combining(ch))
    return stripped.replace("\u0111", "d")


def _tokens(folded: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", folded)


def _phrase_table(phrases: list[str]) -> tuple[tuple[str, str], ...]:
    table = []
    for phrase in phrases:
        table.append((phrase, " ".join(_tokens(fold(phrase)))))
    return tuple(table)


@lru_cache(maxsize=1)
def _rules() -> _Rules:
    data = yaml.safe_load(RULES_PATH.read_text(encoding="utf-8"))
    return _Rules(
        verbs=_phrase_table(data["disable_verbs"]),
        objects=_phrase_table(data["safety_objects"]),
        info=_phrase_table(data["info_markers"]),
        hardware=_phrase_table(data["hardware_markers"]),
        check_words=_phrase_table(data["check_words"]),
        purpose=_phrase_table(data["purpose_markers"]),
        params=tuple(re.compile(p, re.I) for p in data["safety_params"]),
        values=tuple(re.compile(p, re.I) for p in data["value_patterns"]),
        excerpts=tuple(re.compile(p, re.I) for p in data["dangerous_excerpt"]),
    )


def _phrase_hits(tokens: list[str], table: tuple[tuple[str, str], ...]) -> list[str]:
    padded = " " + " ".join(tokens) + " "
    hits = []
    for phrase, phrase_tokens in table:
        if phrase_tokens and (" " + phrase_tokens + " ") in padded:
            hits.append(phrase)
    return list(dict.fromkeys(hits))


def _phrase_positions(tokens: list[str],
                      table: tuple[tuple[str, str], ...]) -> list[tuple[int, int]]:
    """Token spans of every phrase in the table, so proximity can be measured."""
    spans = []
    for _, phrase_tokens in table:
        parts = phrase_tokens.split()
        size = len(parts)
        for index in range(len(tokens) - size + 1):
            if tokens[index:index + size] == parts:
                spans.append((index, index + size - 1))
    return spans


def _regex_hits(folded: str, patterns: tuple[re.Pattern[str], ...]) -> list[str]:
    hits = [match.group(0) for pattern in patterns if (match := pattern.search(folded))]
    return list(dict.fromkeys(hits))


@dataclass
class Verdict:
    dangerous: bool
    matches: list[str] = field(default_factory=list)
    why: list[str] = field(default_factory=list)
    informational: bool = False
    branch: str = "answer"

    def as_dict(self) -> dict:
        return {"dangerous": self.dangerous, "matches": self.matches, "why": self.why,
                "informational": self.informational, "branch": self.branch}


def classify(text: str) -> Verdict:
    """Decide whether a request asks for a safety-disabling workaround."""
    rules = _rules()
    folded = fold(text)
    tokens = _tokens(folded)

    verb_hits = _phrase_hits(tokens, rules.verbs)
    object_hits = _phrase_hits(tokens, rules.objects) + _regex_hits(folded, rules.params)
    object_hits = list(dict.fromkeys(object_hits))
    value_hits = _regex_hits(folded, rules.values)
    info_hits = _phrase_hits(tokens, rules.info)

    dangerous = bool((verb_hits and object_hits) or (object_hits and value_hits))
    why: list[str] = []
    if verb_hits and object_hits:
        why.append(f"{', '.join(verb_hits)} -> {', '.join(object_hits)}: removes a protection "
                   "instead of fixing the cause it reports")
    if object_hits and value_hits:
        why.append(f"{', '.join(value_hits)} -> {', '.join(object_hits)}: zeroing a safety limit "
                   "leaves the vehicle unprotected")
    matches = list(dict.fromkeys(verb_hits + object_hits + value_hits))

    branch = "refuse" if dangerous else ("informational" if info_hits else "answer")
    return Verdict(dangerous=dangerous, matches=matches, why=why,
                   informational=bool(info_hits), branch=branch)


def hardware_procedure(text: str) -> bool:
    """True when the text describes a bench/hardware step, which needs the props-off line."""
    return bool(_phrase_hits(_tokens(fold(text)), _rules().hardware))


def excerpt_is_dangerous(text: str) -> bool:
    """True when a citation excerpt quotes how to disarm a check, which a refusal must not show."""
    low = (text or "").lower()
    if "value 0" in low and "disable" in low:
        return True
    rules = _rules()
    if any(pattern.search(low) for pattern in rules.excerpts):
        return True
    # Proximity rule: a turn-off verb close to a safety object is a recipe, even inside a warning
    # ("it is possible to skip a failing check"). Same vocabulary as the request gate.
    tokens = _tokens(fold(text))
    objects = _phrase_positions(tokens, rules.objects)
    for verb_start, verb_end in _phrase_positions(tokens, rules.verbs):
        for obj_start, obj_end in objects:
            if min(abs(verb_start - obj_start), abs(verb_end - obj_end)) <= EXCERPT_WINDOW:
                return True
    return bool(objects and _regex_hits(fold(text), rules.values))


def safe_citations(results: list[dict], limit: int = 3) -> list[dict]:
    """Keep only citations that explain the purpose of a check, never the disabling recipe."""
    rules = _rules()
    kept = []
    for item in results:
        excerpt = item.get("excerpt") or ""
        if excerpt_is_dangerous(excerpt):
            continue
        tokens = _tokens(fold(excerpt))
        # Purpose-only: talk about a check AND say why it exists. A chunk that merely uses
        # "safety"/"battery" is off-topic for a refusal.
        if not (_phrase_hits(tokens, rules.check_words)
                and _phrase_hits(tokens, rules.purpose)):
            continue
        kept.append(item)
        if len(kept) >= limit:
            break
    return kept


def safety_block(action: str = "<action>", board: str = "<board>",
                 include_props_off: bool = True) -> dict:
    """The bench-test block. The props-off line is conditional: only gate or hardware answers."""
    if include_props_off:
        return {"props_off": PROPS_OFF,
                "confirm": CONFIRM_TEMPLATE.format(action=action, board=board)}
    return {"props_off": None, "confirm": None, "applies": False,
            "note": "No bench procedure in this answer; the props-off line applies to hardware "
                    "steps only."}


def refusal_payload(verdict: Verdict, *, lang: str = "vi") -> dict:
    return {
        "found": True,
        "dangerous": True,
        "refused_as_fix": True,
        "safety_branch": "refuse",
        "language": lang,
        "matches": verdict.matches,
        "why_dangerous": verdict.why,
        "message": REFUSAL_VI if lang == "vi" else REFUSAL_EN,
        "message_en": REFUSAL_EN,
        "safe_path": list(SAFE_PATH),
        "safety": safety_block(),
        "note": "It is fine to ask what a safety parameter does; this refusal only covers using "
                "it to bypass a check.",
    }
