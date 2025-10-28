"""Main entry point for academic paper translation."""

import logging
import os
import sys

from dotenv import load_dotenv

from src import config
from src.core.streaming_translator import StreamingTranslator
from src.utils.text_preprocessor import TextPreprocessor

load_dotenv()

# Configure logging before anything else
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s: %(message)s"
)
logger = logging.getLogger(__name__)


def main() -> None:
    """Main function for text preprocessing, translation, and output formatting."""
    # 0. API 키 확인
    if not os.environ.get("OPENAI_API_KEY"):
        logger.error("에러: OPENAI_API_KEY 환경 변수가 설정되지 않았습니다.")
        logger.error(
            ".env 파일에 OPENAI_API_KEY를 추가하거나 환경 변수를 직접 설정해주세요."
        )
        sys.exit(1)

    # 1. 텍스트 전처리
    preprocessor = TextPreprocessor()
    preprocessor.run()

    # 2. 번역
    try:
        translator = StreamingTranslator(input_file=config.INPUT_FILE)
        metrics = translator.translate()

        # 3. 출력 포맷팅
        translator.format_output()

        logger.info(
            "번역 요약 - 성공: %d개, 실패: %d개, 소요 시간: %.2f초",
            metrics.successes,
            metrics.failures,
            metrics.duration_seconds,
        )
        if metrics.failures > 0:
            logger.warning(
                "일부 번역 청크가 실패했습니다. 로그를 확인하고 재시도를 고려하세요."
            )
            sys.exit(2)

        logger.info("모든 작업이 완료되었습니다.")
    except Exception:
        logger.exception("번역 과정에서 예상치 못한 오류가 발생했습니다")
        sys.exit(1)


if __name__ == "__main__":
    main()
