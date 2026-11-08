"""Tests for the thesis-translate CLI."""

from unittest.mock import patch

from src.main import main


def test_extract_writes_blocks_to_output(tmp_path):
    out = tmp_path / "input.txt"

    with patch("src.main.extract_pdf_text", return_value="Body.\fMore."):
        code = main(["extract", "paper.pdf", "--start-page", "10", "-o", str(out)])

    assert code == 0
    assert out.read_text(encoding="utf-8") == (
        "  p.10\n\n  Body.\n\n  p.11\n\n  More.\n\n"
    )


def test_extract_defaults_to_configured_input_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    with patch("src.main.extract_pdf_text", return_value="Body."):
        code = main(["extract", "paper.pdf"])

    assert code == 0
    assert (tmp_path / "_trimmed_text.txt").read_text(encoding="utf-8") == (
        "  p.1\n\n  Body.\n\n"
    )


def test_extract_returns_error_when_extraction_fails():
    with patch("src.main.extract_pdf_text", side_effect=RuntimeError("no poppler")):
        assert main(["extract", "paper.pdf"]) == 1


def test_verify_passes_for_aligned_files(tmp_path):
    src = tmp_path / "src.txt"
    dst = tmp_path / "dst.txt"
    src.write_text("  p.1\n\n  A.\n\n", encoding="utf-8")
    dst.write_text("  p.1\n\n  가.\n\n", encoding="utf-8")

    assert main(["verify", "--source", str(src), "--translation", str(dst)]) == 0


def test_verify_fails_for_misaligned_files(tmp_path):
    src = tmp_path / "src.txt"
    dst = tmp_path / "dst.txt"
    src.write_text("  p.1\n\n  A.\n\n  B.\n\n", encoding="utf-8")
    dst.write_text("  p.1\n\n  가.\n\n", encoding="utf-8")

    assert main(["verify", "--source", str(src), "--translation", str(dst)]) == 1


def test_format_indents_output_file(tmp_path):
    dst = tmp_path / "dst.txt"
    dst.write_text("p.1\n\n가.\n", encoding="utf-8")

    assert main(["format", str(dst)]) == 0
    assert dst.read_text(encoding="utf-8") == "  p.1\n\n  가.\n"
