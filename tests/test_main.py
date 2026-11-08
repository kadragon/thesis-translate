"""Tests for the thesis-translate CLI."""

from unittest.mock import patch

from src.main import main


def test_extract_names_input_after_pdf(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    with patch("src.main.extract_pdf_text", return_value="Body.\fMore.") as ext:
        code = main(["extract", "/papers/Lacy 2022.pdf", "--start-page", "10"])

    assert code == 0
    ext.assert_called_once_with("/papers/Lacy 2022.pdf", first_pdf_page=1)
    assert (tmp_path / "Lacy 2022_en.txt").read_text(encoding="utf-8") == (
        "  p.10\n\n  Body.\n\n  p.11\n\n  More.\n\n"
    )


def test_extract_passes_first_pdf_page(tmp_path):
    out = tmp_path / "in.txt"

    with patch("src.main.extract_pdf_text", return_value="Body.") as ext:
        main(["extract", "paper.pdf", "--first-pdf-page", "2", "-o", str(out)])

    ext.assert_called_once_with("paper.pdf", first_pdf_page=2)


def test_extract_refuses_to_overwrite_existing_input(tmp_path):
    out = tmp_path / "in.txt"
    out.write_text("cleaned by hand", encoding="utf-8")

    with patch("src.main.extract_pdf_text", return_value="Body."):
        code = main(["extract", "paper.pdf", "-o", str(out)])

    assert code == 1
    assert out.read_text(encoding="utf-8") == "cleaned by hand"


def test_extract_overwrites_with_force(tmp_path):
    out = tmp_path / "in.txt"
    out.write_text("old", encoding="utf-8")

    with patch("src.main.extract_pdf_text", return_value="Body."):
        code = main(["extract", "paper.pdf", "-o", str(out), "--force"])

    assert code == 0
    assert out.read_text(encoding="utf-8") == "  p.1\n\n  Body.\n\n"


def test_extract_returns_error_when_extraction_fails(tmp_path):
    out = tmp_path / "in.txt"
    with patch("src.main.extract_pdf_text", side_effect=RuntimeError("no poppler")):
        assert main(["extract", "paper.pdf", "-o", str(out)]) == 1


def test_verify_passes_for_aligned_files(tmp_path):
    src = tmp_path / "src.txt"
    dst = tmp_path / "dst.txt"
    src.write_text("  p.1\n\n  A.\n\n", encoding="utf-8")
    dst.write_text("  p.1\n\n  가.\n\n", encoding="utf-8")

    assert main(["verify", str(src), str(dst)]) == 0


def test_verify_fails_for_misaligned_files(tmp_path):
    src = tmp_path / "src.txt"
    dst = tmp_path / "dst.txt"
    src.write_text("  p.1\n\n  A.\n\n  B.\n\n", encoding="utf-8")
    dst.write_text("  p.1\n\n  가.\n\n", encoding="utf-8")

    assert main(["verify", str(src), str(dst)]) == 1


def test_verify_warns_but_passes_on_untranslated_paragraph(tmp_path, caplog):
    src = tmp_path / "src.txt"
    dst = tmp_path / "dst.txt"
    src.write_text("  p.1\n\n  A.\n\n", encoding="utf-8")
    dst.write_text("  p.1\n\n  Still English.\n\n", encoding="utf-8")

    with patch("src.main.configure_logging"):
        assert main(["verify", str(src), str(dst)]) == 0
    assert "Still English." in caplog.text


def test_format_indents_output_file(tmp_path):
    dst = tmp_path / "dst.txt"
    dst.write_text("p.1\n\n가.\n", encoding="utf-8")

    assert main(["format", str(dst)]) == 0
    assert dst.read_text(encoding="utf-8") == "  p.1\n\n  가.\n"
