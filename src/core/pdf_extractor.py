"""Extract paper text from a PDF into page-marked paragraph blocks."""

from __future__ import annotations

import re
import statistics
import subprocess
import xml.etree.ElementTree as ET
from collections import Counter
from dataclasses import dataclass
from itertools import pairwise
from pathlib import Path

_INDENT = "  "
_SENTENCE_END = (".", "?", "!", ":", '"', "'", "”", "’", ")")  # noqa: RUF001
_PAGE_NUMBER = re.compile(r"^\d+$")
_XML_INVALID = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")  # pdftotext leaks these
# Layout thresholds in PDF points (1/72 in).
_INDENT_PT = 4.0  # first-line indent / hanging outdent
_JUSTIFIED_SLACK_PT = 2.0  # a "full" line ends this close to the block's right edge
_SHORT_LINE_FRACTION = 0.1  # a last line ends this far (share of width) before it


def extract_pdf_text(pdf_path: str, first_pdf_page: int = 1) -> str:
    """Return the PDF text with blank lines between paragraphs and form feeds
    between pages.

    Paragraphs come from pdftotext's word coordinates (``-bbox-layout``), so
    layouts that separate paragraphs only by indentation -- e.g. two-column IEEE
    papers -- still split correctly. Column order follows pdftotext's flows, which
    handles one-column, two-column and mixed pages alike.

    ``first_pdf_page`` skips leading PDF pages such as a download cover sheet.
    """
    if not Path(pdf_path).is_file():
        msg = f"PDF file not found: {pdf_path}"
        raise FileNotFoundError(msg)
    try:
        result = subprocess.run(
            [
                "pdftotext",
                "-enc",
                "UTF-8",
                "-bbox-layout",
                *(["-f", str(first_pdf_page)] if first_pdf_page > 1 else []),
                pdf_path,
                "-",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
    except FileNotFoundError as exc:
        msg = "pdftotext not found; install poppler (e.g. `brew install poppler`)"
        raise RuntimeError(msg) from exc
    return layout_to_text(result.stdout)


@dataclass(frozen=True)
class _Line:
    x0: float
    x1: float
    y0: float
    y1: float
    text: str


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _children(element: ET.Element, name: str) -> list[ET.Element]:
    return [child for child in element if _local(child.tag) == name]


def _parse_line(element: ET.Element) -> _Line:
    words = [word.text or "" for word in _children(element, "word")]
    return _Line(
        x0=float(element.get("xMin", 0)),
        x1=float(element.get("xMax", 0)),
        y0=float(element.get("yMin", 0)),
        y1=float(element.get("yMax", 0)),
        text=" ".join(word for word in words if word),
    )


def _ends_sentence(text: str) -> bool:
    return text.rstrip().endswith(_SENTENCE_END)


def _split_block(lines: list[_Line]) -> list[list[_Line]]:
    """Split one pdftotext block into paragraphs using line geometry."""
    counts = Counter(round(line.x0) for line in lines)
    top = max(counts.values())
    margin = min(x for x, n in counts.items() if n == top)
    right = max(line.x1 for line in lines)
    width = max(right - margin, 1.0)
    full = sum(line.x1 >= right - _JUSTIFIED_SLACK_PT for line in lines)
    justified = full * 2 >= len(lines)
    heights = [line.y1 - line.y0 for line in lines]
    gaps = [b.y0 - a.y1 for a, b in pairwise(lines)]
    gap_limit = (
        statistics.median(gaps) + statistics.median(heights) / 2 if gaps else 0.0
    )

    paragraphs: list[list[_Line]] = [[lines[0]]]
    for prev, line in pairwise(lines):
        current = paragraphs[-1]
        prev_short = prev.x1 < right - _SHORT_LINE_FRACTION * width
        prev_centered = (
            prev.x0 > margin + _INDENT_PT and prev.x1 < right - _JUSTIFIED_SLACK_PT
        )
        # Indent after a finished sentence or after a heading-like line.
        indented = line.x0 > margin + _INDENT_PT and (
            _ends_sentence(prev.text) or prev_short or prev_centered
        )
        hanging = line.x0 < prev.x0 - _INDENT_PT and len(current) >= 2  # noqa: PLR2004
        short_end = justified and prev_short and _ends_sentence(prev.text)
        gap = line.y0 - prev.y1 > gap_limit
        if indented or hanging or short_end or gap:
            paragraphs.append([line])
        else:
            current.append(line)
    return paragraphs


def _page_text(page: ET.Element) -> str:
    paragraphs: list[str] = []
    for flow in _children(page, "flow"):
        for block in _children(flow, "block"):
            lines = [
                line for line in map(_parse_line, _children(block, "line")) if line.text
            ]
            if lines:
                paragraphs.extend(
                    "\n".join(line.text for line in group)
                    for group in _split_block(lines)
                )
    return "\n\n".join(paragraphs)


def layout_to_text(xhtml: str) -> str:
    """Convert ``pdftotext -bbox-layout`` output into blank-line paragraphs.

    Pages are separated (and terminated) by form feeds, matching plain pdftotext.
    """
    if not xhtml.strip():
        return ""
    root = ET.fromstring(_XML_INVALID.sub("", xhtml))  # local pdftotext output
    pages = [element for element in root.iter() if _local(element.tag) == "page"]
    return "".join(f"{_page_text(page)}\f" for page in pages)


def split_pages(raw: str) -> list[str]:
    """Split pdftotext output into pages, dropping the trailing empty page."""
    pages = raw.split("\f")
    if pages and not pages[-1].strip():
        pages.pop()
    return pages


def _join(left: str, right: str) -> str:
    if left.endswith("-") and left[-2:-1].isalnum():
        # Lowercase continuation is a line-break hyphen; otherwise keep it.
        return left[:-1] + right if right[:1].islower() else left + right
    return f"{left} {right}"


def _paragraphs(page: str) -> list[str]:
    paragraphs: list[str] = []
    current = ""
    for raw_line in [*page.split("\n"), ""]:
        line = raw_line.strip()
        if line:
            current = _join(current, line) if current else line
            continue
        if current and not _PAGE_NUMBER.match(current):
            if paragraphs and _is_continuation(paragraphs[-1], current):
                paragraphs[-1] = _join(paragraphs[-1], current)
            else:
                paragraphs.append(current)
        current = ""
    return paragraphs


def _is_continuation(previous: str, following: str) -> bool:
    return not previous.endswith(_SENTENCE_END) and following[:1].islower()


def build_blocks(pages: list[str], start_page: int) -> list[str]:
    """Build blocks: a ``p.N`` marker before each page, then its paragraphs.

    A paragraph cut off by a column or page break (no closing punctuation, next
    part starting in lowercase) is joined; across pages it moves to the later page.
    """
    page_paragraphs = [_paragraphs(page) for page in pages]
    for current, following in pairwise(page_paragraphs):
        if current and following and _is_continuation(current[-1], following[0]):
            following[0] = _join(current.pop(), following[0])

    blocks: list[str] = []
    for offset, paragraphs in enumerate(page_paragraphs):
        blocks.append(f"p.{start_page + offset}")
        blocks.extend(paragraphs)
    return blocks


def write_blocks(blocks: list[str], output_path: str) -> None:
    """Write blocks in the input-file format: indented, blank line between."""
    Path(output_path).write_text(
        "".join(f"{_INDENT}{block}\n\n" for block in blocks), encoding="utf-8"
    )
