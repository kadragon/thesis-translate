"""CLI for preparing papers for Claude translation and checking the result."""

from __future__ import annotations

import argparse
import logging

from src import config
from src.core.alignment import find_misalignments, read_blocks
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
    try:
        raw = extract_pdf_text(args.pdf)
    except (FileNotFoundError, RuntimeError, OSError) as exc:
        logger.error("PDF 추출 실패: %s", exc)  # noqa: TRY400
        return 1
    blocks = build_blocks(split_pages(raw), start_page=args.start_page)
    write_blocks(blocks, args.output)
    logger.info("%d개 블록을 %s에 저장했습니다.", len(blocks), args.output)
    return 0


def _verify(args: argparse.Namespace) -> int:
    problems = find_misalignments(
        read_blocks(args.source), read_blocks(args.translation)
    )
    for problem in problems:
        logger.error(problem)
    if problems:
        return 1
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
    extract.add_argument("--start-page", type=int, default=1)
    extract.add_argument("-o", "--output", default=config.INPUT_FILE)
    extract.set_defaults(handler=_extract)

    verify = sub.add_parser("verify", help="원문·번역문 구조 일치 확인")
    verify.add_argument("--source", default=config.INPUT_FILE)
    verify.add_argument("--translation", default=config.OUTPUT_FILE)
    verify.set_defaults(handler=_verify)

    fmt = sub.add_parser("format", help="번역 파일 들여쓰기 정리")
    fmt.add_argument("file", nargs="?", default=config.OUTPUT_FILE)
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
