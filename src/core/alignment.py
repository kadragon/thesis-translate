"""Check that a translation keeps the source's paragraph and page structure."""

from __future__ import annotations

import re
from pathlib import Path

_PAGE_MARKER = re.compile(r"^p\.\d+$")
_PREAMBLE = "(before first page marker)"
_HANGUL = re.compile(r"[\uac00-\ud7a3]")


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


def find_untranslated(translation: list[str]) -> list[str]:
    """Return ``"<page> #<n>: <text>"`` for paragraphs containing no Hangul."""
    found: list[str] = []
    label, index = _PREAMBLE, 0
    for block in translation:
        if _PAGE_MARKER.match(block):
            label, index = block, 0
            continue
        index += 1
        if not _HANGUL.search(block):
            found.append(f"{label} #{index}: {block[:60]}")
    return found
