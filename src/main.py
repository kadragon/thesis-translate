"""CLI for preparing papers for Claude translation and checking the result."""

from __future__ import annotations

import argparse
import logging
import subprocess
from pathlib import Path
from xml.etree.ElementTree import ParseError

from src.core.alignment import (
    find_figure_ref_mismatches,
    find_length_outliers,
    find_misalignments,
    find_number_mismatches,
    find_term_violations,
    find_untranslated,
    interleave,
    load_terms,
    read_blocks,
)
from src.core.pdf_extractor import (
    build_blocks,
    extract_pdf_text,
    split_pages,
    write_blocks,
)
from src.utils.output_formatter import OutputFormatter
from src.utils.rich_logging import configure_logging

logger = logging.getLogger(__name__)

_INDENT = "  "
# The shared glossary lives at the repo root, wherever the CLI is run from.
PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _glossary() -> Path:
    return PROJECT_ROOT / "glossary.json"


def _sibling(source: str, suffix: str) -> Path:
    """``paper_en.txt`` -> ``paper<suffix>`` next to it (else ``<stem><suffix>``)."""
    path = Path(source)
    stem = (
        path.name.removesuffix("_en.txt")
        if path.name.endswith("_en.txt")
        else (path.stem)
    )
    return path.with_name(f"{stem}{suffix}")


def _compounds() -> list[str]:
    """Glossary terms for hyphen repair; extraction never fails on the glossary."""
    try:
        return [entry["term"] for entry in load_terms([_glossary()])]
    except ValueError as exc:
        logger.warning("용어 파일 오류(하이픈 복원에 쓰지 않음): %s", exc)
        return []


def _extract(args: argparse.Namespace) -> int:
    output = args.output or f"{Path(args.pdf).stem}_en.txt"
    if Path(output).exists() and not args.force:
        logger.error("%s 파일이 이미 있습니다. 덮어쓰려면 --force를 쓰세요.", output)
        return 1
    try:
        raw = extract_pdf_text(args.pdf, first_pdf_page=args.first_pdf_page)
    except (
        FileNotFoundError,
        RuntimeError,
        OSError,
        subprocess.CalledProcessError,
        ParseError,
    ) as exc:
        # pdftotext's own message (encrypted, broken xref) says more than its exit code.
        stderr = getattr(exc, "stderr", None)
        logger.error("PDF 추출 실패: %s", stderr.strip() if stderr else exc)  # noqa: TRY400
        return 1
    pages = split_pages(raw)
    blank = sum(1 for page in pages if not page.strip())
    if not pages or blank * 2 > len(pages):
        logger.error(
            "텍스트가 없는 쪽이 %d/%d쪽입니다. 스캔본으로 보이며 OCR이 필요합니다.",
            blank,
            len(pages),
        )
        return 1
    blocks = build_blocks(pages, start_page=args.start_page, compounds=_compounds())
    write_blocks(blocks, output)
    logger.info("%d개 블록을 %s에 저장했습니다.", len(blocks), output)
    return 0


def _verify(args: argparse.Namespace) -> int:
    source = read_blocks(args.source)
    translation = read_blocks(args.translation)
    problems = find_misalignments(source, translation)
    for problem in problems:
        logger.error(problem)
    for block in find_untranslated(translation):
        logger.warning("한글 없음: %s", block)
    if problems:
        return 1
    term_paths = (
        [Path(path) for path in args.glossary]
        if args.glossary
        else [_glossary(), _sibling(args.source, "_terms.json")]
    )
    try:
        terms = load_terms(term_paths)
    except ValueError as exc:
        logger.error("용어 파일 오류: %s", exc)  # noqa: TRY400
        return 1
    for outlier in find_length_outliers(source, translation):
        logger.warning("길이 이상(누락 의심): %s", outlier)
    for mismatch in find_number_mismatches(source, translation):
        logger.warning("숫자 불일치: %s", mismatch)
    for mismatch in find_figure_ref_mismatches(source, translation):
        logger.warning("그림·표 참조: %s", mismatch)
    for violation in find_term_violations(source, translation, terms):
        logger.warning("용어 불일치: %s", violation)
    logger.info("원문과 번역문의 문단·페이지 구조가 일치합니다.")
    return 0


def _dual(args: argparse.Namespace) -> int:
    source = read_blocks(args.source)
    translation = read_blocks(args.translation)
    problems = find_misalignments(source, translation)
    if problems:
        for problem in problems:
            logger.error(problem)
        return 1
    output = Path(args.output) if args.output else _sibling(args.source, "_dual.txt")
    output.write_text(
        "".join(
            "".join(f"{_INDENT}{line}\n" for line in group) + "\n"
            for group in interleave(source, translation)
        ),
        encoding="utf-8",
    )
    logger.info("원문 병기본을 %s에 저장했습니다.", output)
    return 0


def _format(args: argparse.Namespace) -> int:
    OutputFormatter.format_output(args.file)
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="thesis-translate")
    sub = parser.add_subparsers(dest="command", required=True)

    extract = sub.add_parser("extract", help="PDF를 문단 블록 입력 파일로 추출")
    extract.add_argument("pdf")
    extract.add_argument(
        "--start-page", type=int, default=1, help="첫 페이지의 인쇄된 쪽 번호"
    )
    extract.add_argument(
        "--first-pdf-page",
        type=int,
        default=1,
        help="추출을 시작할 PDF 쪽(표지 건너뛰기)",
    )
    extract.add_argument("-o", "--output", help="기본값: <PDF 이름>_en.txt")
    extract.add_argument("--force", action="store_true", help="기존 파일 덮어쓰기")
    extract.set_defaults(handler=_extract)

    verify = sub.add_parser("verify", help="원문·번역문 구조 일치 확인")
    verify.add_argument("source")
    verify.add_argument("translation")
    verify.add_argument(
        "--glossary",
        action="append",
        help="용어 파일(반복 가능). 기본값: glossary.json, <PDF 이름>_terms.json",
    )
    verify.set_defaults(handler=_verify)

    dual = sub.add_parser("dual", help="원문·번역문 병기본 만들기")
    dual.add_argument("source")
    dual.add_argument("translation")
    dual.add_argument("-o", "--output", help="기본값: <PDF 이름>_dual.txt")
    dual.set_defaults(handler=_dual)

    fmt = sub.add_parser("format", help="번역 파일 들여쓰기 정리")
    fmt.add_argument("file")
    fmt.set_defaults(handler=_format)
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the CLI and return the process exit code."""
    configure_logging()
    args = _parser().parse_args(argv)
    try:
        code: int = args.handler(args)
    except FileNotFoundError as exc:
        logger.error("파일을 찾을 수 없습니다: %s", exc.filename or exc)  # noqa: TRY400
        return 1
    return code


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
