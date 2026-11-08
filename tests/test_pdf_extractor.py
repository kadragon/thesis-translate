"""Tests for PDF text extraction into paragraph blocks."""

import subprocess
from unittest.mock import patch

import pytest

from src.core.pdf_extractor import (
    build_blocks,
    extract_pdf_text,
    split_pages,
    write_blocks,
)


def test_split_pages_on_form_feed_drops_trailing_empty_page():
    assert split_pages("page one\fpage two\f") == ["page one", "page two"]


def test_build_blocks_puts_page_marker_before_page_content():
    pages = ["First para.\n\nSecond para.", "Third para."]

    assert build_blocks(pages, start_page=174) == [
        "p.174",
        "First para.",
        "Second para.",
        "p.175",
        "Third para.",
    ]


def test_build_blocks_joins_wrapped_lines_with_spaces():
    pages = ["Humans are\ncreatures of\nhabit."]

    assert build_blocks(pages, start_page=1) == [
        "p.1",
        "Humans are creatures of habit.",
    ]


def test_build_blocks_removes_line_break_hyphen_before_lowercase():
    pages = ["when imple-\nmented, it works."]

    assert build_blocks(pages, start_page=1) == ["p.1", "when implemented, it works."]


def test_build_blocks_keeps_hyphen_before_uppercase_or_digit():
    pages = ["Evidence-\nBased care in 2021-\n2022."]

    assert build_blocks(pages, start_page=1) == [
        "p.1",
        "Evidence-Based care in 2021-2022.",
    ]


def test_build_blocks_drops_standalone_page_numbers():
    pages = ["Body text.\n\n174"]

    assert build_blocks(pages, start_page=174) == ["p.174", "Body text."]


def test_build_blocks_moves_unfinished_paragraph_to_next_page():
    pages = ["Done.\n\nThis sentence continues", "on the next page.\n\nNew para."]

    assert build_blocks(pages, start_page=1) == [
        "p.1",
        "Done.",
        "p.2",
        "This sentence continues on the next page.",
        "New para.",
    ]


def test_build_blocks_merges_hyphenated_paragraph_across_pages():
    pages = ["It was imple-", "mented well."]

    assert build_blocks(pages, start_page=1) == [
        "p.1",
        "p.2",
        "It was implemented well.",
    ]


def test_build_blocks_keeps_paragraph_when_next_page_starts_uppercase():
    pages = ["Heading without period", "New section."]

    assert build_blocks(pages, start_page=1) == [
        "p.1",
        "Heading without period",
        "p.2",
        "New section.",
    ]


def test_build_blocks_emits_marker_for_empty_page():
    assert build_blocks(["", "Text."], start_page=1) == ["p.1", "p.2", "Text."]


def test_write_blocks_uses_indented_paragraph_format(tmp_path):
    out = tmp_path / "input.txt"

    write_blocks(["p.1", "Body."], str(out))

    assert out.read_text(encoding="utf-8") == "  p.1\n\n  Body.\n\n"


def test_extract_pdf_text_invokes_pdftotext(tmp_path):
    pdf = tmp_path / "paper.pdf"
    pdf.write_bytes(b"%PDF")
    completed = subprocess.CompletedProcess([], 0, stdout="text\f", stderr="")

    with patch("src.core.pdf_extractor.subprocess.run", return_value=completed) as run:
        assert extract_pdf_text(str(pdf)) == "text\f"

    args = run.call_args.args[0]
    assert args[0] == "pdftotext"
    assert str(pdf) in args
    assert args[-1] == "-"
    assert "-f" not in args


def test_extract_pdf_text_starts_from_first_pdf_page(tmp_path):
    pdf = tmp_path / "paper.pdf"
    pdf.write_bytes(b"%PDF")
    completed = subprocess.CompletedProcess([], 0, stdout="", stderr="")

    with patch("src.core.pdf_extractor.subprocess.run", return_value=completed) as run:
        extract_pdf_text(str(pdf), first_pdf_page=2)

    args = run.call_args.args[0]
    assert args[args.index("-f") + 1] == "2"


def test_extract_pdf_text_raises_when_pdf_missing(tmp_path):
    with pytest.raises(FileNotFoundError, match="PDF"):
        extract_pdf_text(str(tmp_path / "missing.pdf"))


def test_extract_pdf_text_explains_missing_pdftotext(tmp_path):
    pdf = tmp_path / "paper.pdf"
    pdf.write_bytes(b"%PDF")

    with (
        patch("src.core.pdf_extractor.subprocess.run", side_effect=FileNotFoundError),
        pytest.raises(RuntimeError, match="poppler"),
    ):
        extract_pdf_text(str(pdf))


def test_build_blocks_merges_column_break_within_page():
    pages = ["Left column ends mid\n\nsentence in the right column.\n\nNext."]

    assert build_blocks(pages, start_page=1) == [
        "p.1",
        "Left column ends mid sentence in the right column.",
        "Next.",
    ]
