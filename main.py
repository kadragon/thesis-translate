
import logging
from core.batch_translator import BatchTranslator
from utils.text_preprocessor import TextPreprocessor
from utils.format_output import add_leading_spaces_to_file

def main():
    # 1. 텍스트 전처리
    preprocessor = TextPreprocessor()
    preprocessor.run()

    # 2. 번역
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s %(levelname)s: %(message)s')
    
    batch_translator = BatchTranslator(
        input_file=TextPreprocessor.FILE_NAME
    )
    batch_translator.translate()

    # 3. 출력 포맷팅
    add_leading_spaces_to_file(batch_translator.output_file)

    print("모든 작업이 완료되었습니다.")

if __name__ == "__main__":
    main()
