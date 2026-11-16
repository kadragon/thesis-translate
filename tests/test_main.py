"""Tests for the thesis-translate CLI."""

import logging
import subprocess
from unittest.mock import patch
from xml.etree.ElementTree import ParseError

import pytest

from src.main import main
from src.utils.rich_logging import configure_logging, get_console


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


def test_verify_warns_but_passes_on_short_translation(tmp_path, caplog):
    src = tmp_path / "src.txt"
    dst = tmp_path / "dst.txt"
    body = "Long sentence here. " * 20
    src.write_text(f"  p.1\n\n  {body}\n\n", encoding="utf-8")
    dst.write_text("  p.1\n\n  짧다.\n\n", encoding="utf-8")

    with patch("src.main.configure_logging"):
        assert main(["verify", str(src), str(dst)]) == 0
    assert "길이 이상" in caplog.text


def test_extract_refuses_pdf_without_text_layer(tmp_path):
    out = tmp_path / "in.txt"

    with patch("src.main.extract_pdf_text", return_value="\f \fBody.\f"):
        code = main(["extract", "scan.pdf", "-o", str(out)])

    assert code == 1
    assert not out.exists()


def _write(path, text):
    path.write_text(text, encoding="utf-8")
    return str(path)


def test_verify_warns_on_number_figure_and_term_problems(tmp_path, caplog):
    src = _write(
        tmp_path / "paper_en.txt",
        "  p.1\n\n  Machine unlearning on 50 tasks (Figure 2).\n\n",
    )
    dst = _write(tmp_path / "paper_ko.txt", "  p.1\n\n  기계 망각을 40개 과제에서.\n\n")
    _write(
        tmp_path / "paper_terms.json",
        '[{"term": "unlearning", "translation": "언러닝"}]',
    )

    with patch("src.main.configure_logging"):
        assert main(["verify", src, dst]) == 0
    assert "숫자 불일치" in caplog.text
    assert "그림 2 없음" in caplog.text
    assert "unlearning → 언러닝 없음" in caplog.text


def test_verify_uses_explicit_glossary_option(tmp_path, caplog):
    src = _write(tmp_path / "s.txt", "  p.1\n\n  A transformer.\n\n")
    dst = _write(tmp_path / "d.txt", "  p.1\n\n  변환기.\n\n")
    gloss = _write(
        tmp_path / "g.json", '[{"term": "transformer", "translation": "트랜스포머"}]'
    )

    with patch("src.main.configure_logging"):
        assert main(["verify", src, dst, "--glossary", gloss]) == 0
    assert "transformer → 트랜스포머 없음" in caplog.text


def test_verify_fails_on_malformed_terms_file(tmp_path):
    src = _write(tmp_path / "s.txt", "  p.1\n\n  A.\n\n")
    dst = _write(tmp_path / "d.txt", "  p.1\n\n  가.\n\n")
    gloss = _write(tmp_path / "g.json", '{"not": "a list"}')

    assert main(["verify", src, dst, "--glossary", gloss]) == 1


def test_dual_writes_interleaved_file_named_after_source(tmp_path):
    src = _write(tmp_path / "paper_en.txt", "  p.1\n\n  A.\n\n  B.\n\n")
    dst = _write(tmp_path / "paper_ko.txt", "  p.1\n\n  가.\n\n  나.\n\n")

    assert main(["dual", src, dst]) == 0
    assert (tmp_path / "paper_dual.txt").read_text(encoding="utf-8") == (
        "  p.1\n\n  A.\n  가.\n\n  B.\n  나.\n\n"
    )


def test_dual_refuses_misaligned_files(tmp_path):
    src = _write(tmp_path / "paper_en.txt", "  p.1\n\n  A.\n\n  B.\n\n")
    dst = _write(tmp_path / "paper_ko.txt", "  p.1\n\n  가.\n\n")

    assert main(["dual", src, dst]) == 1
    assert not (tmp_path / "paper_dual.txt").exists()


def test_format_indents_output_file(tmp_path):
    dst = tmp_path / "dst.txt"
    dst.write_text("p.1\n\n가.\n", encoding="utf-8")

    assert main(["format", str(dst)]) == 0
    assert dst.read_text(encoding="utf-8") == "  p.1\n\n  가.\n"


def test_extract_reports_pdftotext_failure_without_traceback(tmp_path):
    out = tmp_path / "in.txt"
    error = subprocess.CalledProcessError(1, ["pdftotext"])
    with patch("src.main.extract_pdf_text", side_effect=error):
        assert main(["extract", "paper.pdf", "-o", str(out)]) == 1


def test_extract_reports_malformed_layout_without_traceback(tmp_path):
    out = tmp_path / "in.txt"
    with patch("src.main.extract_pdf_text", side_effect=ParseError("bad")):
        assert main(["extract", "paper.pdf", "-o", str(out)]) == 1


def test_configure_logging_prints_brackets_literally():
    configure_logging()
    console = get_console()
    with console.capture() as capture:
        logging.getLogger("t").error("source [p.1, p.2], we use [i] and [b]")

    assert "[p.1, p.2], we use [i] and [b]" in capture.get()


def test_extract_reports_pdftotext_stderr(tmp_path, caplog):
    out = tmp_path / "in.txt"
    error = subprocess.CalledProcessError(
        1, ["pdftotext"], stderr="Syntax Error: Couldn't read xref table\n"
    )
    with (
        patch("src.main.configure_logging"),
        patch("src.main.extract_pdf_text", side_effect=error),
    ):
        assert main(["extract", "paper.pdf", "-o", str(out)]) == 1

    assert "Couldn't read xref table" in caplog.text


@pytest.mark.parametrize(
    "command",
    [
        ["verify", "missing_en.txt", "missing_ko.txt"],
        ["dual", "missing_en.txt", "missing_ko.txt"],
        ["format", "missing_ko.txt"],
    ],
)
def test_commands_report_missing_input_file(tmp_path, monkeypatch, caplog, command):
    monkeypatch.chdir(tmp_path)

    with patch("src.main.configure_logging"):
        assert main(command) == 1
    assert "missing_" in caplog.text


def test_verify_default_glossary_resolves_from_project_root(
    tmp_path, monkeypatch, caplog
):
    root = tmp_path / "repo"
    root.mkdir()
    _write(
        root / "glossary.json",
        '[{"term": "transformer", "translation": "트랜스포머"}]',
    )
    work = tmp_path / "elsewhere"
    work.mkdir()
    src = _write(work / "s.txt", "  p.1\n\n  A transformer.\n\n")
    dst = _write(work / "d.txt", "  p.1\n\n  변환기.\n\n")
    monkeypatch.chdir(work)

    with (
        patch("src.main.PROJECT_ROOT", root),
        patch("src.main.configure_logging"),
    ):
        assert main(["verify", src, dst]) == 0
    assert "transformer → 트랜스포머 없음" in caplog.text


def test_glossary_env_overrides_the_project_root_glossary(
    tmp_path, monkeypatch, caplog
):
    root = tmp_path / "repo"
    root.mkdir()
    _write(root / "glossary.json", "not json")
    snapshot = _write(
        tmp_path / "snap.json",
        '[{"term": "transformer", "translation": "트랜스포머"}]',
    )
    work = tmp_path / "elsewhere"
    work.mkdir()
    src = _write(work / "s.txt", "  p.1\n\n  A transformer.\n\n")
    dst = _write(work / "d.txt", "  p.1\n\n  변환기.\n\n")
    monkeypatch.chdir(work)
    monkeypatch.setenv("THESIS_TRANSLATE_GLOSSARY", str(snapshot))

    with (
        patch("src.main.PROJECT_ROOT", root),
        patch("src.main.configure_logging"),
    ):
        assert main(["verify", src, dst]) == 0
    assert "transformer → 트랜스포머 없음" in caplog.text


def test_extract_keeps_glossary_compound_hyphen(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    _write(root / "glossary.json", '[{"term": "long-term", "translation": "장기"}]')
    out = tmp_path / "paper_en.txt"

    with (
        patch("src.main.PROJECT_ROOT", root),
        patch("src.main.extract_pdf_text", return_value="A long-\nterm study.\f"),
        patch("src.main.configure_logging"),
    ):
        assert main(["extract", "paper.pdf", "-o", str(out)]) == 0
    assert "A long-term study." in out.read_text(encoding="utf-8")


def test_extract_warns_and_continues_on_malformed_glossary(tmp_path, caplog):
    root = tmp_path / "repo"
    root.mkdir()
    _write(root / "glossary.json", '{"not": "a list"}')
    out = tmp_path / "paper_en.txt"

    with (
        patch("src.main.PROJECT_ROOT", root),
        patch("src.main.extract_pdf_text", return_value="A long-\nterm study.\f"),
        patch("src.main.configure_logging"),
    ):
        assert main(["extract", "paper.pdf", "-o", str(out)]) == 0
    assert "용어 파일 오류" in caplog.text
    assert "A longterm study." in out.read_text(encoding="utf-8")


def _term_files(tmp_path, monkeypatch, paper_translation):
    monkeypatch.chdir(tmp_path)
    _write(
        tmp_path / "glossary.json",
        '[{"term": "unlearning", "translation": "언러닝"},'
        ' {"term": "habit", "translation": "습관"}]',
    )
    _write(
        tmp_path / "paper_terms.json",
        f'[{{"term": "Unlearning", "translation": "{paper_translation}"}},'
        ' {"term": "habit", "translation": "습관"}]',
    )
    return ["glossary.json", "paper_terms.json"]


def test_terms_check_reports_conflict_and_fails(tmp_path, monkeypatch, caplog):
    caplog.set_level(logging.INFO)
    files = _term_files(tmp_path, monkeypatch, "탈학습")
    before = [(tmp_path / f).read_bytes() for f in files]

    with patch("src.main.configure_logging"):
        assert main(["terms-check", *files]) == 1
    assert (
        "용어 충돌: unlearning → 언러닝 (glossary.json #1) 채택,"
        " Unlearning → 탈학습 (paper_terms.json #1) 가려짐"
    ) in caplog.text
    assert "같은 번역어 중복: habit → 습관 (paper_terms.json #2)" in caplog.text
    assert [(tmp_path / f).read_bytes() for f in files] == before


def test_terms_check_passes_with_only_duplicates(tmp_path, monkeypatch, caplog):
    caplog.set_level(logging.INFO)
    files = _term_files(tmp_path, monkeypatch, "언러닝")

    with patch("src.main.configure_logging"):
        assert main(["terms-check", *files]) == 0
    assert "용어 충돌" not in caplog.text
    assert "같은 번역어 중복: Unlearning → 언러닝" in caplog.text


def test_terms_check_fails_on_malformed_file(tmp_path, caplog):
    bad = _write(tmp_path / "g.json", '{"not": "a list"}')

    with patch("src.main.configure_logging"):
        assert main(["terms-check", bad]) == 1
    assert "용어 파일 오류" in caplog.text


def test_terms_check_fails_on_missing_named_file(tmp_path, caplog):
    gloss = _write(tmp_path / "g.json", '[{"term": "a", "translation": "가"}]')

    with patch("src.main.configure_logging"):
        assert main(["terms-check", gloss, str(tmp_path / "typo.json")]) == 1
    assert "typo.json" in caplog.text


def test_terms_check_names_file_with_invalid_json(tmp_path, caplog):
    bad = _write(tmp_path / "paper_terms.json", '[{"term": "a",}]')

    with patch("src.main.configure_logging"):
        assert main(["terms-check", bad]) == 1
    assert "paper_terms.json" in caplog.text


def test_terms_check_ignores_repeated_path(tmp_path, monkeypatch, caplog):
    files = _term_files(tmp_path, monkeypatch, "언러닝")
    caplog.set_level(logging.INFO)

    with patch("src.main.configure_logging"):
        assert main(["terms-check", *files, "./glossary.json"]) == 0
    assert "같은 번역어 중복 2건" in caplog.text


def test_terms_check_reports_unreadable_file(tmp_path, caplog):
    gloss = _write(tmp_path / "g.json", "[]")

    with (
        patch("src.main.configure_logging"),
        patch(
            "src.core.alignment.Path.read_text",
            side_effect=PermissionError(13, "denied"),
        ),
    ):
        assert main(["terms-check", gloss]) == 1
    assert "용어 파일 오류" in caplog.text


def test_terms_check_source_uses_verify_paths(tmp_path, monkeypatch, caplog):
    _term_files(tmp_path, monkeypatch, "탈학습")
    monkeypatch.delenv("THESIS_TRANSLATE_GLOSSARY", raising=False)
    _write(tmp_path / "paper_en.txt", "")

    with (
        patch("src.main.PROJECT_ROOT", tmp_path),
        patch("src.main.configure_logging"),
    ):
        assert main(["terms-check", "--source", "paper_en.txt"]) == 1
    assert "glossary.json #1) 채택" in caplog.text
    assert "paper_terms.json #1) 가려짐" in caplog.text


def test_terms_check_defaults_to_glossary_env(tmp_path, monkeypatch, caplog):
    snapshot = _write(
        tmp_path / "snapshot.json",
        '[{"term": "a", "translation": "가"}, {"term": "A", "translation": "나"}]',
    )
    monkeypatch.setenv("THESIS_TRANSLATE_GLOSSARY", snapshot)

    with patch("src.main.configure_logging"):
        assert main(["terms-check"]) == 1
    assert "snapshot.json #2) 가려짐" in caplog.text


def test_terms_check_source_skips_missing_paper_terms(tmp_path, monkeypatch, caplog):
    caplog.set_level(logging.INFO)
    gloss = _write(tmp_path / "g.json", '[{"term": "a", "translation": "가"}]')
    monkeypatch.setenv("THESIS_TRANSLATE_GLOSSARY", gloss)
    source = _write(tmp_path / "paper_en.txt", "")

    with patch("src.main.configure_logging"):
        code = main(["terms-check", "--source", source])
    assert code == 0
    assert "충돌 0건" in caplog.text


ARGPARSE_USAGE_ERROR = 2


def test_terms_check_rejects_files_with_source(tmp_path):
    gloss = _write(tmp_path / "g.json", "[]")

    with patch("src.main.configure_logging"), pytest.raises(SystemExit) as exc:
        main(["terms-check", gloss, "--source", "paper_en.txt"])
    assert exc.value.code == ARGPARSE_USAGE_ERROR


def test_terms_check_fails_on_missing_source(tmp_path, monkeypatch, caplog):
    gloss = _write(tmp_path / "g.json", "[]")
    monkeypatch.setenv("THESIS_TRANSLATE_GLOSSARY", gloss)

    with patch("src.main.configure_logging"):
        assert main(["terms-check", "--source", str(tmp_path / "papr_en.txt")]) == 1
    assert "papr_en.txt" in caplog.text


def test_terms_check_names_skipped_defaults(tmp_path, monkeypatch, caplog):
    caplog.set_level(logging.INFO)
    monkeypatch.setenv("THESIS_TRANSLATE_GLOSSARY", str(tmp_path / "gone.json"))

    with patch("src.main.configure_logging"):
        assert main(["terms-check"]) == 0
    assert "gone.json" in caplog.text
    assert "검사할 용어 파일이 없습니다" in caplog.text
