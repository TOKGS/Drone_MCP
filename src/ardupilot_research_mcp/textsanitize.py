"""Text sanitising for indexed content and returned excerpts.

Two jobs:
1. Blank per-file licence/copyright headers before chunking, while keeping the line count
   identical so every cited line range still points at the real file (blanks are stripped by
   the fidelity audit on both sides, so quotes still match).
2. Strip control characters and ANSI escapes from anything returned to a client.
"""

from __future__ import annotations

import re

LICENSE_MARKERS = re.compile(
    r"(?i)(gnu\s+(lesser\s+)?general\s+public\s+license|copyright\s+\(c\)|"
    r"spdx-license-identifier|this\s+program\s+is\s+free\s+software|"
    r"licensed\s+under|all\s+rights\s+reserved|mit\s+license|apache\s+license|"
    r"mozilla\s+public\s+license|redistribution\s+and\s+use)"
)

CODE_PREFIXES = ("#include", "#define", "#if", "#ifdef", "#ifndef", "#pragma",
                 "#else", "#endif", "#undef")
COMMENT_PREFIXES = ("/*", "//", "#", '"""', "'''", "--", ";", "*")
CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
ANSI = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")


def _leading_block_end(lines: list[str], start: int, max_scan: int) -> int:
    """Index one past the end of the leading comment block starting at `start`."""
    first = lines[start].strip()
    limit = min(len(lines), start + max_scan)
    if first.startswith("/*"):
        index = start
        while index < limit:
            if "*/" in lines[index]:
                return index + 1
            index += 1
        return limit
    if first.startswith(('"""', "'''")):
        quote = first[:3]
        if lines[start].count(quote) >= 2:
            return start + 1
        index = start + 1
        while index < limit:
            if quote in lines[index]:
                return index + 1
            index += 1
        return limit
    index = start
    while index < limit:
        stripped = lines[index].strip()
        if stripped.startswith(CODE_PREFIXES):
            break
        if stripped and not stripped.startswith(COMMENT_PREFIXES):
            break
        index += 1
    return index


def blank_license_header(text: str, max_scan: int = 80) -> str:
    """Replace a leading licence comment block with blank lines (line count preserved)."""
    lines = text.splitlines()
    start = 0
    while start < len(lines) and not lines[start].strip():
        start += 1
    if start >= len(lines):
        return text
    first = lines[start].strip()
    if not first.startswith(COMMENT_PREFIXES):
        return text
    end = _leading_block_end(lines, start, max_scan)
    if end <= start:
        return text
    block = range(start, end)
    if not any(LICENSE_MARKERS.search(lines[line]) for line in block):
        return text
    cleaned = list(lines)
    for line in block:
        cleaned[line] = ""
    result = "\n".join(cleaned)
    return result + "\n" if text.endswith("\n") else result


def strip_control(text: str) -> str:
    """Remove ANSI escapes and control characters; keep tabs and newlines."""
    return CONTROL.sub("", ANSI.sub("", text))


def sanitize_excerpt(text: str) -> str:
    return strip_control(text)


# --------------------------------------------------------------------------- distillation
# Distillation feeds the search index only. The verbatim chunk text is never modified, so
# every excerpt can still be checked against `git show <sha>:<path>`.

RST_DIRECTIVE = re.compile(r"^\.\.\s+(image|figure|toctree|raw|include|only|meta|contents|"
                           r"sectnum|code-block|literalinclude)::")
RST_ADMONITION = re.compile(r"^\.\.\s+(note|warning|tip|important|caution|danger|hint|seealso)::")
RST_TARGET = re.compile(r"^\.\.\s+_[^:]*:\s*$")
RST_ROLE = re.compile(r":(ref|doc|abbr|term|meth|class|func|mod|attr|data|option|envvar|"
                      r"command|program|file|kbd|guilabel|menuselection|sup|sub|math):`([^`]*)`")
RST_LINK = re.compile(r"`([^`<]+)\s*<[^>]+>`_")
MD_IMAGE = re.compile(r"!\[[^\]]*\]\([^)]*\)")
MD_LINK = re.compile(r"\[([^\]]+)\]\([^)]*\)")
HTML_TAG = re.compile(r"</?[A-Za-z][^>]*>")
ANCHOR = re.compile(r"^\s*_`([^`]+)`\s*$")


def _drop_keys(words: list[tuple[int, str]], drop: set[int]) -> list[str]:
    return [word for index, word in words if index not in drop]


def distill_for_search(rel_path: str, text: str) -> str:
    """Condensed, markup-free text used for BM25 only (never cited, never compared to Git)."""
    suffix = rel_path.rsplit(".", 1)[-1].lower() if "." in rel_path else ""
    lines = text.splitlines()

    cleaned: list[str] = []
    skip_indent: int | None = None
    for line in lines:
        stripped = line.strip()
        indent = len(line) - len(line.lstrip())
        if skip_indent is not None:
            if not stripped or indent > skip_indent:
                continue
            skip_indent = None
        if suffix == "rst":
            if RST_DIRECTIVE.match(stripped) or RST_ADMONITION.match(stripped):
                skip_indent = indent
                continue
            if RST_TARGET.match(stripped):
                continue
            line = RST_ROLE.sub(lambda m: m.group(2), line)
            line = RST_LINK.sub(lambda m: m.group(1), line)
            match = ANCHOR.match(line)
            if match:
                line = match.group(1)
            if re.fullmatch(r"[=\-~^\"'`#*+]{3,}", stripped or "x"):
                continue
        line = MD_IMAGE.sub("", line)
        line = MD_LINK.sub(lambda m: m.group(1), line)
        line = HTML_TAG.sub("", line)
        if stripped:
            cleaned.append(line)

    body = "\n".join(cleaned)
    body = blank_license_header(body)
    body = re.sub(r"[ \t]{2,}", " ", body)
    body = re.sub(r"\n{3,}", "\n\n", body)
    return strip_control(body).strip()
