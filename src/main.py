import logging
import os
import sys

from dotenv import load_dotenv

from src import config
from src.core.normal_translator import NormalTranslator
from src.utils.text_preprocessor import TextPreprocessor

load_dotenv()

# Configure logging before anything else
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s: %(message)s"
)
logger = logging.getLogger(__name__)


def main():
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
        normal_translator = NormalTranslator(input_file=config.INPUT_FILE)
        normal_translator.translate()

        # 3. 출력 포맷팅
        normal_translator.format_output()

        print("모든 작업이 완료되었습니다.")
    except Exception as e:
        logger.exception(f"번역 과정에서 예상치 못한 오류가 발생했습니다: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
