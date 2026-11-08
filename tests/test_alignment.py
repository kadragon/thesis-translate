"""Tests for source/translation block alignment checks."""

from src.core.alignment import find_misalignments, read_blocks


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
