"""Extract paper text from a PDF into page-marked paragraph blocks."""

from __future__ import annotations

import re
import subprocess
from itertools import pairwise
from pathlib import Path

_INDENT = "  "
_SENTENCE_END = (".", "?", "!", ":", '"', "'", "”", "’", ")")  # noqa: RUF001
_PAGE_NUMBER = re.compile(r"^\d+$")


def extract_pdf_text(pdf_path: str) -> str:
    """Return the PDF text from pdftotext, with pages separated by form feeds."""
    if not Path(pdf_path).is_file():
        msg = f"PDF file not found: {pdf_path}"
        raise FileNotFoundError(msg)
    try:
        result = subprocess.run(
            ["pdftotext", "-enc", "UTF-8", pdf_path, "-"],
            capture_output=True,
            text=True,
            check=True,
        )
    except FileNotFoundError as exc:
        msg = "pdftotext not found; install poppler (e.g. `brew install poppler`)"
        raise RuntimeError(msg) from exc
    return result.stdout


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
