"""Check that a translation keeps the source's paragraph and page structure."""

from __future__ import annotations

import json
import re
from collections import Counter
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
# Thousands-grouped numbers stay whole; other commas (citation lists) split.
_NUMBER = re.compile(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?(?!\d)|\d+(?:\.\d+)?")
# (source pattern, Korean label) for figure/table references.
_FIGURE_REFS = (
    # Any case for the word; Roman numerals stay uppercase so "table civil" is no ref.
    (re.compile(r"\b(?i:fig(?:ure)?s?)\.?\s*(\d+)"), "그림"),
    (re.compile(r"\b(?i:tables?)\s+(\d+|[IVXLC]+)\b"), "표"),
)


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


def find_number_mismatches(source: list[str], translation: list[str]) -> list[str]:
    """Return blocks where a source number (value, year, citation) is missing.

    Numbers are compared as multisets, since Korean word order may move them.
    Extra numbers alone are fine (``ten`` is often written ``10`` in Korean);
    they are listed only next to a missing one, where they hint at a typo.
    Assumes the two block lists are already aligned.
    """
    found: list[str] = []
    for label, index, src, dst in _labeled_pairs(source, translation):
        src_numbers = Counter(_NUMBER.findall(src))
        dst_numbers = Counter(_NUMBER.findall(dst))
        if not src_numbers - dst_numbers:
            continue
        missing = ", ".join((src_numbers - dst_numbers).elements())
        extra = ", ".join((dst_numbers - src_numbers).elements())
        found.append(
            f"{label} #{index}: missing [{missing}], extra [{extra}]: {src[:60]}"
        )
    return found


def find_figure_ref_mismatches(source: list[str], translation: list[str]) -> list[str]:
    """Return blocks where ``Figure N``/``Table N`` lacks ``그림 N``/``표 N``.

    Assumes the two block lists are already aligned.
    """
    found: list[str] = []
    for label, index, src, dst in _labeled_pairs(source, translation):
        found.extend(
            f"{label} #{index}: {korean} {number} 없음: {src[:60]}"
            for pattern, korean in _FIGURE_REFS
            for number in dict.fromkeys(pattern.findall(src))
            if not re.search(rf"{korean}\s*{number}(?![\dIVXLC])", dst)
        )
    return found


def load_terms(paths: list[Path]) -> list[dict[str, str]]:
    """Merge ``[{"term", "translation"}]`` files in order, skipping missing ones.

    A term repeated later (case-insensitive) is dropped, so the shared glossary
    listed first wins over a paper's term table.
    Raises ``ValueError`` naming the file when its content is malformed.
    """
    terms: dict[str, dict[str, str]] = {}
    for path in paths:
        if not path.is_file():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, list) or not all(
            isinstance(entry, dict)
            and isinstance(entry.get("term"), str)
            and isinstance(entry.get("translation"), str)
            for entry in data
        ):
            msg = f'{path}: expected [{{"term": ..., "translation": ...}}]'
            raise ValueError(msg)
        for entry in data:
            terms.setdefault(
                entry["term"].casefold(),
                {"term": entry["term"], "translation": entry["translation"]},
            )
    return list(terms.values())


def find_term_violations(
    source: list[str], translation: list[str], terms: list[dict[str, str]]
) -> list[str]:
    """Return blocks whose source uses a term but whose translation lacks its
    fixed Korean rendering. Plural ``-s``/``-es`` forms count as the term.

    Assumes the two block lists are already aligned.
    """
    patterns = [
        (
            re.compile(
                rf"\b{re.escape(entry['term'])}(?:s|es)?\b",
                # All-caps acronyms (IT, US) would otherwise match common words.
                0 if entry["term"].isupper() else re.IGNORECASE,
            ),
            entry,
        )
        for entry in terms
    ]
    found: list[str] = []
    for label, index, src, dst in _labeled_pairs(source, translation):
        found.extend(
            f"{label} #{index}: {entry['term']} → {entry['translation']} 없음: "
            f"{src[:60]}"
            for pattern, entry in patterns
            if pattern.search(src) and entry["translation"] not in dst
        )
    return found


def interleave(source: list[str], translation: list[str]) -> list[list[str]]:
    """Group aligned blocks: ``[marker]`` for page markers, else ``[src, dst]``."""
    return [
        [src] if _PAGE_MARKER.match(src) else [src, dst]
        for src, dst in zip(source, translation, strict=True)
    ]
