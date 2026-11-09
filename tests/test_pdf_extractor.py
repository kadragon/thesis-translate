"""Tests for PDF text extraction into paragraph blocks."""

import subprocess
from unittest.mock import patch

import pytest

from src.core.pdf_extractor import (
    build_blocks,
    extract_pdf_text,
    layout_to_text,
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


def test_build_blocks_keeps_hyphen_of_compound_seen_elsewhere():
    pages = [
        "A self-supervised model.\n\nWe train self-\nsupervised and pre-\ntrained nets."
    ]

    assert build_blocks(pages, start_page=1) == [
        "p.1",
        "A self-supervised model.",
        "We train self-supervised and pretrained nets.",
    ]


def test_build_blocks_keeps_hyphen_of_compound_across_pages():
    pages = ["Self-Supervised.\n\nIt is self-", "supervised here."]

    assert build_blocks(pages, start_page=1)[-1] == "It is self-supervised here."


def test_build_blocks_keeps_hyphen_of_glossary_compound():
    pages = ["A long-\nterm study."]

    assert build_blocks(pages, start_page=1, compounds={"Long-Term"}) == [
        "p.1",
        "A long-term study.",
    ]


def test_build_blocks_keeps_hyphen_of_multi_hyphen_and_digit_compounds():
    pages = [
        "A state-of-the-art, end-to-end, COVID-19-related model.\n\n"
        "Our state-of-the-\nart, end-to-\nend, COVID-19-\nrelated, "
        "non-end-to-\nend nets."
    ]

    assert build_blocks(pages, start_page=1)[-1] == (
        "Our state-of-the-art, end-to-end, COVID-19-related, non-end-to-end nets."
    )


def test_build_blocks_keeps_hyphen_of_compound_inside_multiword_glossary_term():
    pages = ["A long-\nterm memory."]

    assert build_blocks(pages, start_page=1, compounds=["long-term memory"]) == [
        "p.1",
        "A long-term memory.",
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


def test_extract_pdf_text_converts_bbox_layout(tmp_path):
    pdf = tmp_path / "paper.pdf"
    pdf.write_bytes(b"%PDF")
    layout = _doc(_page(_flow(_block(_line(50, 300, 10, "Body.")))))
    completed = subprocess.CompletedProcess([], 0, stdout=layout, stderr="")

    with patch("src.core.pdf_extractor.subprocess.run", return_value=completed) as run:
        assert extract_pdf_text(str(pdf)) == "Body.\f"

    args = run.call_args.args[0]
    assert args[0] == "pdftotext"
    assert "-bbox-layout" in args
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


# --- bbox-layout paragraph detection -------------------------------------------


def _line(x0, x1, y, text, height=9.0):
    words = "".join(
        f'<word xMin="{x0}" yMin="{y}" xMax="{x1}" yMax="{y + height}">{w}</word>'
        for w in text.split()
    )
    box = f'xMin="{x0}" yMin="{y}" xMax="{x1}" yMax="{y + height}"'
    return f"<line {box}>{words}</line>"


def _block(*lines):
    return f'<block xMin="0" yMin="0" xMax="0" yMax="0">{"".join(lines)}</block>'


def _flow(*blocks):
    return f"<flow>{''.join(blocks)}</flow>"


def _page(*flows):
    return f'<page width="612" height="792">{"".join(flows)}</page>'


def _doc(*pages):
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN"'
        ' "http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">\n'
        '<html xmlns="http://www.w3.org/1999/xhtml"><head><title></title></head>'
        f"<body><doc>{''.join(pages)}</doc></body></html>"
    )


def test_layout_splits_indented_paragraphs_in_two_column_page():
    left = _block(
        _line(59, 300, 10, "First paragraph starts"),
        _line(49, 300, 22, "and ends here."),
        _line(59, 300, 34, "Second paragraph"),
        _line(49, 200, 46, "is short."),
    )
    right = _block(
        _line(322, 563, 10, "Right column paragraph"),
        _line(312, 563, 22, "continues."),
    )

    assert layout_to_text(_doc(_page(_flow(left), _flow(right)))) == (
        "First paragraph starts\nand ends here.\n\n"
        "Second paragraph\nis short.\n\n"
        "Right column paragraph\ncontinues.\f"
    )


def test_layout_keeps_wrapped_line_that_follows_unfinished_sentence():
    block = _block(
        _line(49, 300, 10, "A sentence that wraps"),
        _line(59, 300, 22, "onto an indented line."),
    )

    assert layout_to_text(_doc(_page(_flow(block)))) == (
        "A sentence that wraps\nonto an indented line.\f"
    )


def test_layout_starts_new_item_at_each_hanging_indent():
    block = _block(
        _line(49, 300, 10, "• First item text"),
        _line(58, 300, 22, "wraps here."),
        _line(49, 300, 34, "• Second item"),
        _line(58, 250, 46, "also wraps."),
    )

    assert layout_to_text(_doc(_page(_flow(block)))) == (
        "• First item text\nwraps here.\n\n• Second item\nalso wraps.\f"
    )


def test_layout_splits_after_short_last_line_in_justified_text():
    block = _block(
        _line(49, 300, 10, "Justified line one of"),
        _line(49, 300, 22, "a paragraph that ends"),
        _line(49, 180, 34, "here."),
        _line(49, 300, 46, "Unindented next paragraph"),
        _line(49, 300, 58, "keeps the full width"),
        _line(49, 220, 70, "too."),
    )

    assert layout_to_text(_doc(_page(_flow(block)))) == (
        "Justified line one of\na paragraph that ends\nhere.\n\n"
        "Unindented next paragraph\nkeeps the full width\ntoo.\f"
    )


def test_layout_keeps_ragged_right_text_together():
    block = _block(
        _line(49, 290, 10, "Ragged lines end anywhere."),
        _line(49, 300, 22, "Even after a period"),
        _line(49, 260, 34, "the paragraph goes on."),
    )

    assert layout_to_text(_doc(_page(_flow(block)))) == (
        "Ragged lines end anywhere.\nEven after a period\nthe paragraph goes on.\f"
    )


def test_layout_splits_on_large_vertical_gap():
    block = _block(
        _line(49, 300, 10, "First block line"),
        _line(49, 300, 22, "second line"),
        _line(49, 300, 34, "third line"),
        _line(49, 300, 60, "After a gap"),
    )

    assert layout_to_text(_doc(_page(_flow(block)))) == (
        "First block line\nsecond line\nthird line\n\nAfter a gap\f"
    )


def test_layout_separates_pages_and_unescapes_entities():
    first = _page(_flow(_block(_line(49, 300, 10, "Tom &amp; Jerry."))))
    empty = _page()

    assert layout_to_text(_doc(first, empty)) == "Tom & Jerry.\f\f"


def test_layout_drops_control_characters_invalid_in_xml():
    page = _page(_flow(_block(_line(49, 300, 10, "Bad\x02 glyph."))))

    assert layout_to_text(_doc(page)) == "Bad glyph.\f"


def test_layout_splits_heading_line_from_indented_paragraph():
    block = _block(
        _line(49, 180, 10, "A. Section Heading"),
        _line(59, 300, 22, "The paragraph begins"),
        _line(49, 300, 34, "and continues to the"),
        _line(49, 250, 46, "end."),
    )

    assert layout_to_text(_doc(_page(_flow(block)))) == (
        "A. Section Heading\n\nThe paragraph begins\nand continues to the\nend.\f"
    )


def test_layout_splits_centered_heading_from_indented_paragraph():
    block = _block(
        _line(73, 276, 10, "II. CENTERED SECTION HEADING"),
        _line(59, 300, 22, "This section reviews"),
        _line(49, 300, 34, "the formulation and"),
        _line(49, 85, 46, "methods."),
    )

    assert layout_to_text(_doc(_page(_flow(block)))) == (
        "II. CENTERED SECTION HEADING\n\n"
        "This section reviews\nthe formulation and\nmethods.\f"
    )


def test_extract_pdf_text_decodes_output_as_utf8(tmp_path):
    pdf = tmp_path / "paper.pdf"
    pdf.write_bytes(b"%PDF")
    completed = subprocess.CompletedProcess([], 0, stdout="", stderr="")

    with patch("src.core.pdf_extractor.subprocess.run", return_value=completed) as run:
        extract_pdf_text(str(pdf))

    assert run.call_args.kwargs["encoding"] == "utf-8"


def test_layout_keeps_indented_block_quote_lines_together():
    block = _block(
        _line(49, 300, 10, "Prior work has long"),
        _line(49, 300, 22, "argued the same, and"),
        _line(49, 300, 34, "as the authors note:"),
        _line(79, 270, 46, "Learning is a lifelong"),
        _line(79, 270, 58, "Process that never ends"),
        _line(79, 200, 70, "In any domain."),
        _line(49, 300, 82, "We follow that view"),
        _line(49, 300, 94, "throughout the paper"),
        _line(49, 300, 106, "and its experiments."),
    )

    assert layout_to_text(_doc(_page(_flow(block)))).split("\n\n")[1] == (
        "Learning is a lifelong\nProcess that never ends\nIn any domain."
    )
