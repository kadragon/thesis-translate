"""CLI for preparing papers for Claude translation and checking the result."""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from src.core.alignment import (
    find_length_outliers,
    find_misalignments,
    find_untranslated,
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


def _extract(args: argparse.Namespace) -> int:
    output = args.output or f"{Path(args.pdf).stem}_en.txt"
    if Path(output).exists() and not args.force:
        logger.error("%s 파일이 이미 있습니다. 덮어쓰려면 --force를 쓰세요.", output)
        return 1
    try:
        raw = extract_pdf_text(args.pdf, first_pdf_page=args.first_pdf_page)
    except (FileNotFoundError, RuntimeError, OSError) as exc:
        logger.error("PDF 추출 실패: %s", exc)  # noqa: TRY400
        return 1
    blocks = build_blocks(split_pages(raw), start_page=args.start_page)
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
    for outlier in find_length_outliers(source, translation):
        logger.warning("길이 이상(누락 의심): %s", outlier)
    logger.info("원문과 번역문의 문단·페이지 구조가 일치합니다.")
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
    verify.set_defaults(handler=_verify)

    fmt = sub.add_parser("format", help="번역 파일 들여쓰기 정리")
    fmt.add_argument("file")
    fmt.set_defaults(handler=_format)
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the CLI and return the process exit code."""
    configure_logging()
    args = _parser().parse_args(argv)
    code: int = args.handler(args)
    return code


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
