
import logging
from core.file_translator import FileTranslator
from core.openai_translator import OpenAITranslator
from utils.text_preprocessor import TextPreprocessor
from utils.format_output import add_leading_spaces_to_file

def main():
    # 1. 텍스트 전처리
    preprocessor = TextPreprocessor()
    preprocessor.run()

    # 2. 번역
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s %(levelname)s: %(message)s')
    translator = OpenAITranslator(glossary_path='glossary.json')
    file_translator = FileTranslator(
        input_file=TextPreprocessor.FILE_NAME,
        translator=translator.translate
    )
    file_translator.buffer_translate_and_save()

    # 3. 출력 포맷팅
    add_leading_spaces_to_file(file_translator.output_file)

    print("모든 작업이 완료되었습니다.")

if __name__ == "__main__":
    main()
