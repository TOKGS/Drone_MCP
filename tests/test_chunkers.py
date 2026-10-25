"""Chunker tests: line ranges must point back at the exact source lines."""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from ardupilot_research_mcp.ingest.chunk import (  # noqa: E402
    chunk_code, chunk_hwdef, chunk_markdown, chunk_for_path)

MARKDOWN = """# Board bring-up

Intro paragraph about the board.

## Serial ports

SERIAL1_PROTOCOL selects the protocol.

```cpp
// a fence must never be split
void setup() { SERIAL_ORDER; }
```

## RC input

RC_OPTIONS bit 9 enables the CRSF telemetry.
"""

HWdef = """# CubeOrangePlus hwdef
MCU STM32H743VI

SERIAL_ORDER OTG1 USART2 USART3 UART4 UART7

define HAL_GPIO_LED_PIN 25
"""

CODE = """#include <cstdio>

// a comment block that belongs to the first function
int alpha(int x)
{
    if (x > 0) {
        return x;
    }
    return 0;
}

int beta(int y)
{
    return y * 2;
}
"""


def test_markdown_line_ranges_round_trip() -> None:
    lines = MARKDOWN.splitlines()
    chunks = chunk_markdown(MARKDOWN)
    assert chunks, "no chunks produced"
    for piece in chunks:
        actual = "\n".join(lines[piece.line_start - 1:piece.line_end])
        assert actual.strip() == piece.text.strip(), (piece.line_start, piece.line_end)


def test_markdown_heading_path_tracks_sections() -> None:
    chunks = chunk_markdown(MARKDOWN)
    paths = {piece.heading_path for piece in chunks}
    assert "Board bring-up > Serial ports" in paths
    assert any(path.endswith("RC input") for path in paths)


def test_code_fence_is_not_split() -> None:
    chunks = chunk_markdown(MARKDOWN)
    fence_chunks = [c for c in chunks if "```cpp" in c.text]
    assert fence_chunks, "fence block missing"
    for chunk in fence_chunks:
        assert chunk.text.count("```") % 2 == 0, chunk.text


def test_code_line_ranges_round_trip() -> None:
    lines = CODE.splitlines()
    for piece in chunk_code(CODE):
        actual = "\n".join(lines[piece.line_start - 1:piece.line_end])
        assert actual.strip() == piece.text.strip()


def test_hwdef_small_file_merges_and_large_file_splits() -> None:
    lines = HWdef.splitlines()
    small = chunk_hwdef(HWdef)
    assert len(small) == 1, "a short hwdef should stay one chunk (target 300-900 chars)"
    for piece in small:
        actual = "\n".join(lines[piece.line_start - 1:piece.line_end])
        assert actual.strip() == piece.text.strip()

    big_lines = []
    for index in range(60):
        big_lines += [f"# section {index}", f"define HAL_FEATURE_{index}_ENABLED 1",
                      f"define HAL_PIN_{index} {index * 7}", ""]
    big = "\n".join(big_lines)
    chunks = chunk_hwdef(big)
    assert len(chunks) > 1, "a 60-section hwdef must be split"
    big_source = big.splitlines()
    for piece in chunks:
        actual = "\n".join(big_source[piece.line_start - 1:piece.line_end])
        assert actual.strip() == piece.text.strip()
        assert len(piece.text) <= 900 + 200  # merged blocks stay near the target


def test_dispatch_by_path() -> None:
    assert chunk_for_path("libraries/AP_HAL_ChibiOS/hwdef/X/hwdef.dat", HWdef)
    assert chunk_for_path("docs/setup.md", MARKDOWN)
    assert chunk_for_path("libraries/AP_RCProtocol/AP_RCProtocol.cpp", CODE)


def test_no_chunk_exceeds_hard_cap() -> None:
    """A generated array never closes its brace; the size cap must still cut it."""
    generated = "const char page[] = {\n" + "\n".join(f"0x{i:02x}," for i in range(4000)) + "\n};\n"
    chunks = chunk_code(generated)
    assert len(chunks) > 1
    assert max(len(c.text) for c in chunks) < 6000
