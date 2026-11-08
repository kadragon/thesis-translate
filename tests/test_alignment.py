"""Tests for source/translation block alignment checks."""

from src.core.alignment import (
    find_length_outliers,
    find_misalignments,
    find_untranslated,
    read_blocks,
)


def test_read_blocks_returns_stripped_non_empty_lines(tmp_path):
    path = tmp_path / "f.txt"
    path.write_text("  p.1\n\n  Body one.\n\n\n  Body two.\n\n", encoding="utf-8")

    assert read_blocks(str(path)) == ["p.1", "Body one.", "Body two."]


def test_find_misalignments_accepts_matching_structure():
    source = ["Title", "p.1", "A.", "B.", "p.2", "C."]
    translation = ["제목", "p.1", "가.", "나.", "p.2", "다."]

    assert find_misalignments(source, translation) == []


def test_find_misalignments_reports_page_with_missing_paragraph():
    source = ["p.1", "A.", "B.", "p.2", "C."]
    translation = ["p.1", "가.", "p.2", "다."]

    assert find_misalignments(source, translation) == [
        "p.1: source has 2 paragraphs, translation has 1"
    ]


def test_find_misalignments_reports_paragraphs_before_first_marker():
    source = ["Title", "p.1", "A."]
    translation = ["p.1", "가."]

    assert find_misalignments(source, translation) == [
        "(before first page marker): source has 1 paragraphs, translation has 0"
    ]


def test_find_misalignments_reports_marker_sequence_mismatch():
    source = ["p.1", "A.", "p.2", "B."]
    translation = ["p.1", "가.", "p.3", "나."]

    assert find_misalignments(source, translation) == [
        "page markers differ: source [p.1, p.2], translation [p.1, p.3]"
    ]


def test_find_untranslated_lists_blocks_without_hangul():
    translation = ["p.1", "가.", "Alicia M. Pike Lacy, PhD", "p.2", "Not translated."]

    assert find_untranslated(translation) == [
        "p.1 #2: Alicia M. Pike Lacy, PhD",
        "p.2 #1: Not translated.",
    ]


def test_find_length_outliers_flags_suspiciously_short_translation():
    long_source = "Word " * 60
    translation_ok = "가" * 150
    translation_short = "가" * 20
    source = ["p.1", long_source, long_source]
    translation = ["p.1", translation_ok, translation_short]

    assert find_length_outliers(source, translation) == [
        f"p.1 #2: ratio 0.07: {long_source[:60]}"
    ]


def test_find_length_outliers_ignores_short_source_paragraphs():
    source = ["p.1", "Figure 1: A caption."]
    translation = ["p.1", "그림 1"]

    assert find_length_outliers(source, translation) == []
