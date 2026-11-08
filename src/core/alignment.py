"""Check that a translation keeps the source's paragraph and page structure."""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator

_PAGE_MARKER = re.compile(r"^p\.\d+$")
_PREAMBLE = "(before first page marker)"
_HANGUL = re.compile(r"[\uac00-\ud7a3]")
# Korean runs ~0.5-0.6x the English character count; far below hints at omission.
_MIN_RATIO = 0.3
_MIN_SOURCE_CHARS = 150


def read_blocks(path: str) -> list[str]:
    """Return the non-empty lines of a file, stripped."""
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    return [line.strip() for line in lines if line.strip()]


def _segments(blocks: list[str]) -> list[tuple[str, int]]:
    segments: list[tuple[str, int]] = [(_PREAMBLE, 0)]
    for block in blocks:
        if _PAGE_MARKER.match(block):
            segments.append((block, 0))
        else:
            label, count = segments[-1]
            segments[-1] = (label, count + 1)
    return segments


def find_misalignments(source: list[str], translation: list[str]) -> list[str]:
    """Return human-readable differences; an empty list means aligned."""
    source_segments = _segments(source)
    translation_segments = _segments(translation)

    source_markers = [label for label, _ in source_segments[1:]]
    translation_markers = [label for label, _ in translation_segments[1:]]
    if source_markers != translation_markers:
        return [
            f"page markers differ: source [{', '.join(source_markers)}], "
            f"translation [{', '.join(translation_markers)}]"
        ]

    return [
        f"{label}: source has {source_count} paragraphs, "
        f"translation has {translation_count}"
        for (label, source_count), (_, translation_count) in zip(
            source_segments, translation_segments, strict=True
        )
        if source_count != translation_count
    ]


def _labeled(blocks: list[str]) -> Iterator[tuple[str, int, str]]:
    """Yield ``(page label, paragraph number, block)`` for non-marker blocks."""
    label, index = _PREAMBLE, 0
    for block in blocks:
        if _PAGE_MARKER.match(block):
            label, index = block, 0
            continue
        index += 1
        yield label, index, block


def _labeled_pairs(
    source: list[str], translation: list[str]
) -> Iterator[tuple[str, int, str, str]]:
    """Yield ``(label, number, source, translation)``; assumes aligned lists."""
    for (label, index, src), dst in zip(
        _labeled(source),
        (block for block in translation if not _PAGE_MARKER.match(block)),
        strict=False,
    ):
        yield label, index, src, dst


def find_untranslated(translation: list[str]) -> list[str]:
    """Return ``"<page> #<n>: <text>"`` for paragraphs containing no Hangul."""
    return [
        f"{label} #{index}: {block[:60]}"
        for label, index, block in _labeled(translation)
        if not _HANGUL.search(block)
    ]


def find_length_outliers(source: list[str], translation: list[str]) -> list[str]:
    """Return ``"<page> #<n>: ratio <r>: <source>"`` for suspiciously short blocks.

    Assumes the two block lists are already aligned.
    """
    found: list[str] = []
    for label, index, src, dst in _labeled_pairs(source, translation):
        if len(src) < _MIN_SOURCE_CHARS:
            continue
        ratio = len(dst) / len(src)
        if ratio < _MIN_RATIO:
            found.append(f"{label} #{index}: ratio {ratio:.2f}: {src[:60]}")
    return found
