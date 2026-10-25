"""Chunkers: markdown/rst by heading, code by block, hwdef by logical section.

Contract: every chunk carries a 1-based inclusive line range into the *original* file,
never splits a fenced code block or a table row, and stays within 300-900 characters
when the source allows it.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

MIN_CHARS = 300
TARGET_CHARS = 600
MAX_CHARS = 900
OVERLAP_LINES = 3

MD_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")
RST_UNDERLINE = re.compile(r"^([=\-~^\"'`#*+:])\1{2,}\s*$")
RST_LEVEL = {"=": 1, "-": 2, "~": 3, "^": 4, '"': 5, "'": 6, "`": 7, "#": 8, "*": 9, "+": 10}

CODE_SUFFIXES = {".c", ".h", ".cpp", ".hpp", ".cc", ".cxx", ".py", ".lua", ".sh",
                 ".ps1", ".cmake", ".ino", ".s", ".ld"}
BLOCK_SUFFIXES = {".yml", ".yaml", ".json", ".xml", ".toml", ".ini", ".cfg", ".conf"}
DOC_SUFFIXES = {".md", ".rst", ".txt"}
# A single generated array (e.g. html/headers/web-*.h) never closes its brace, so a
# depth-only boundary would emit one 300 KB chunk. Hard-cut on size as well.
SIZE_HARD_CAP = 3000


@dataclass
class Chunk:
    text: str
    heading_path: str
    anchor: str | None
    line_start: int
    line_end: int

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.text.encode("utf-8")).hexdigest()


def slugify(title: str) -> str:
    slug = re.sub(r"[^\w\s-]", "", title.lower()).strip()
    return re.sub(r"[\s_]+", "-", slug)


def _slice(lines: list[str], start: int, end: int, heading_path: str,
           anchor: str | None) -> Chunk | None:
    text = "\n".join(lines[start:end]).strip("\n")
    if not text.strip():
        return None
    return Chunk(text=text, heading_path=heading_path, anchor=anchor,
                 line_start=start + 1, line_end=end)


def _pack_paragraphs(lines: list[str], base: int, heading_path: str,
                     anchor: str | None) -> list[Chunk]:
    """Greedy paragraph packing inside one section, never splitting a paragraph."""
    blocks: list[tuple[int, int]] = []
    start = None
    in_fence = False
    for offset, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_fence = not in_fence
        if start is None:
            if stripped:
                start = offset
            continue
        boundary = (not in_fence and not stripped
                    and not (offset + 1 < len(lines) and (lines[offset + 1].strip().startswith("|")
                                                          or lines[offset + 1].startswith("    "))))
        if boundary:
            blocks.append((start, offset))
            start = None
    if start is not None:
        blocks.append((start, len(lines)))

    chunks: list[Chunk] = []
    current: tuple[int, int] | None = None
    for block_start, block_end in blocks:
        if current is None:
            current = (block_start, block_end)
        else:
            merged_len = len("\n".join(lines[current[0]:block_end]))
            if merged_len <= TARGET_CHARS:
                current = (current[0], block_end)
            else:
                chunk = _slice(lines, current[0], current[1], heading_path, anchor)
                if chunk:
                    chunks.append(Chunk(chunk.text, chunk.heading_path, chunk.anchor,
                                        chunk.line_start + base - 1, chunk.line_end + base - 1))
                current = (block_start, block_end)
    if current is not None:
        chunk = _slice(lines, current[0], current[1], heading_path, anchor)
        if chunk:
            chunks.append(Chunk(chunk.text, chunk.heading_path, chunk.anchor,
                                chunk.line_start + base - 1, chunk.line_end + base - 1))
    return _split_oversized(chunks, lines, base, heading_path, anchor)


def _split_oversized(chunks: list[Chunk], lines: list[str], base: int,
                     heading_path: str, anchor: str | None) -> list[Chunk]:
    out: list[Chunk] = []
    for chunk in chunks:
        if len(chunk.text) <= MAX_CHARS:
            out.append(chunk)
            continue
        start = chunk.line_start - 1 - (base - 1)
        end = chunk.line_end - (base - 1)
        piece_start = start
        while piece_start < end:
            piece_end = piece_start
            size = 0
            while piece_end < end and size < TARGET_CHARS:
                size += len(lines[piece_end]) + 1
                piece_end += 1
            piece = _slice(lines, piece_start, piece_end, heading_path, anchor)
            if piece:
                out.append(Chunk(piece.text, heading_path, anchor,
                                 piece_start + base, piece_end + base - 1))
            piece_start = piece_end
    return out


def _headings(lines: list[str]) -> list[tuple[int, str, int, int]]:
    """(level, title, heading_line_index, first_body_index)."""
    found: list[tuple[int, str, int, int]] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        match = MD_HEADING.match(line)
        if match:
            found.append((len(match.group(1)), match.group(2).strip(), index, index + 1))
            index += 1
            continue
        if (index + 1 < len(lines) and line.strip() and len(line.strip()) >= 3):
            underline = RST_UNDERLINE.match(lines[index + 1])
            if underline and len(lines[index + 1].strip()) >= len(line.strip()):
                char = underline.group(1)
                found.append((RST_LEVEL.get(char, 6), line.strip(), index, index + 2))
                index += 2
                continue
        index += 1
    return found


def chunk_markdown(text: str) -> list[Chunk]:
    lines = text.splitlines()
    headings = _headings(lines)
    chunks: list[Chunk] = []
    if not headings:
        chunks.extend(_pack_paragraphs(lines, 1, "", None))
        return [c for c in chunks if c.text.strip()]

    preamble = _pack_paragraphs(lines[:headings[0][2]], 1, "", None)
    chunks.extend(preamble)

    stack: list[tuple[int, str]] = []
    for position, (level, title, heading_index, body_start) in enumerate(headings):
        body_end = headings[position + 1][2] if position + 1 < len(headings) else len(lines)
        while stack and stack[-1][0] >= level:
            stack.pop()
        stack.append((level, title))
        heading_path = " > ".join(item[1] for item in stack)
        anchor = slugify(title)
        section_lines = lines[body_start:body_end]
        for chunk in _pack_paragraphs(section_lines, body_start + 1, heading_path, anchor):
            chunks.append(chunk)
    return [c for c in chunks if c.text.strip()]


def _brace_depth(line: str, depth: int) -> int:
    cleaned = re.sub(r'"(\\.|[^"\\])*"', '""', line)
    cleaned = re.sub(r"'(\\.|[^'\\])*'", "''", cleaned)
    cleaned = re.sub(r"//.*$", "", cleaned)
    return depth + cleaned.count("{") - cleaned.count("}")


def chunk_code(text: str, heading_path: str = "") -> list[Chunk]:
    lines = text.splitlines()
    chunks: list[Chunk] = []
    start = 0
    depth = 0
    size = 0
    index = 0
    while index < len(lines):
        line = lines[index]
        depth = _brace_depth(line, depth)
        size += len(line) + 1
        index += 1
        at_boundary = depth <= 0 and (not line.strip() or line.rstrip().endswith("}"))
        if (size >= TARGET_CHARS and at_boundary) or size >= SIZE_HARD_CAP:
            chunk = _slice(lines, start, index, heading_path, None)
            if chunk:
                chunks.append(chunk)
            start = max(index - OVERLAP_LINES, start + 1)
            size = len("\n".join(lines[start:index]))
    remainder = _slice(lines, start, len(lines), heading_path, None)
    if remainder and remainder.text.strip():
        chunks.append(remainder)
    return chunks


def chunk_hwdef(text: str, heading_path: str = "") -> list[Chunk]:
    lines = text.splitlines()
    blocks: list[tuple[int, int]] = []
    start = None
    for offset, line in enumerate(lines):
        if line.strip():
            if start is None:
                start = offset
        elif start is not None:
            blocks.append((start, offset))
            start = None
    if start is not None:
        blocks.append((start, len(lines)))

    chunks: list[Chunk] = []
    current: tuple[int, int] | None = None
    for block_start, block_end in blocks:
        if current is None:
            current = (block_start, block_end)
        elif len("\n".join(lines[current[0]:block_end])) <= MAX_CHARS:
            current = (current[0], block_end)
        else:
            chunk = _slice(lines, current[0], current[1], heading_path, None)
            if chunk:
                chunks.append(chunk)
            current = (block_start, block_end)
    if current is not None:
        chunk = _slice(lines, current[0], current[1], heading_path, None)
        if chunk and chunk.text.strip():
            chunks.append(chunk)
    return chunks


def chunk_for_path(rel_path: str, text: str) -> list[Chunk]:
    suffix = Path(rel_path).suffix.lower()
    name = Path(rel_path).name.lower()
    if name.endswith("hwdef.dat") or suffix == ".parm":
        return chunk_hwdef(text, heading_path=rel_path)
    if suffix in BLOCK_SUFFIXES:
        return chunk_hwdef(text, heading_path=rel_path)
    if suffix in DOC_SUFFIXES:
        return chunk_markdown(text)
    if suffix in CODE_SUFFIXES:
        return chunk_code(text, heading_path=rel_path)
    return chunk_markdown(text)
