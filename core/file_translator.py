"""
파일 번역 유틸리티

- 지정한 텍스트 파일을 읽어 버퍼 단위로 번역하여 결과 파일에 저장
- 번역 API(예시: OpenAI) 의존성 주입
"""

import logging
from core.openai_translator import OpenAITranslator


class FileTranslator:
    """
    파일을 읽어 지정된 크기만큼 버퍼에 모은 후 번역 API를 통해 번역하고 결과를 파일에 저장하는 클래스.

    Args:
        input_file (str): 번역할 입력 텍스트 파일 경로.
        output_file (str, optional): 번역 결과를 저장할 출력 파일 경로. 기본값은 '_result_text_ko.txt'.
        max_token_length (int, optional): 버퍼 크기 제한 (토큰 수 기준, 임시로 문자열 길이로 계산). 기본값은 8000.
        translator (callable, optional): 번역 기능을 수행하는 함수 또는 객체. 기본값은 openai_api()의 translate 메서드.
    """

    def __init__(self,
                 input_file: str,
                 output_file: str = '_result_text_ko.txt',
                 max_token_length: int = 8000,
                 translator=None):
        """
        FileTranslator 인스턴스를 초기화합니다.

        Args:
            input_file (str): 번역할 입력 파일 경로.
            output_file (str, optional): 번역 결과를 저장할 출력 파일 경로. 기본값은 '_result_text_ko.txt'.
            max_token_length (int, optional): 버퍼 크기 제한 (토큰 수 기준). 기본값은 8000.
            translator (callable, optional): 번역 함수. 기본값은 openai_api().translate.
        """
        self.input_file = input_file
        self.output_file = output_file
        self.max_token_length = max_token_length
        self.translator = translator or OpenAITranslator().translate

    def read_lines(self):
        """
        입력 파일을 읽어 모든 라인을 리스트로 반환합니다.

        Returns:
            list[str]: 입력 파일의 모든 라인 리스트. 파일을 찾지 못하면 빈 리스트를 반환합니다.

        Logs:
            파일을 찾지 못할 경우 에러 로그를 기록합니다.
        """
        try:
            with open(self.input_file, 'r', encoding='utf-8') as file:
                return file.readlines()
        except FileNotFoundError:
            logging.error(f"파일을 찾을 수 없습니다: {self.input_file}")
            return []

    def buffer_translate_and_save(self):
        """
        입력 파일을 라인 단위로 읽어 버퍼에 누적하고, 버퍼 크기가 max_token_length에 도달하면 번역 후 결과를 출력 파일에 저장합니다.

        버퍼에 남은 내용이 있으면 마지막으로 번역하여 저장합니다.

        Logs:
            각 블록 번역 시작 및 완료 시점에 정보 로그를 기록합니다.
            번역 실패 시 에러 로그를 기록합니다.
        """
        lines = self.read_lines()
        buffer = ""
        total_lines = len(lines)
        block_num = 1
        buffer_start_line = 0

        for idx, line in enumerate(lines):
            if line.strip():
                if buffer == "":
                    buffer_start_line = idx

                buffer += "\n" + line

                if self._is_buffer_ready(buffer):
                    # Logging: 번역 시작
                    percent = int((buffer_start_line + 1) /
                                  total_lines * 100) if total_lines > 0 else 0
                    logging.info(
                        f"{block_num}번째 블록 번역 시작 ({buffer_start_line + 1}/{total_lines}, {percent}%)")

                    self._translate_and_write(buffer)
                    logging.info(f"{block_num}번째 블록 번역 완료")

                    block_num += 1
                    buffer = ""

        if buffer.strip():
            percent = int((buffer_start_line + 1) /
                          total_lines * 100) if total_lines > 0 else 0
            logging.info(
                f"{block_num}번째 블록 번역 시작 ({buffer_start_line + 1}/{total_lines}, {percent}%)")
            self._translate_and_write(buffer)
            logging.info(f"{block_num}번째 블록 번역 완료")

    def _is_buffer_ready(self, buffer: str) -> bool:
        """
        현재 버퍼의 길이가 max_token_length 이상인지 판단합니다.

        Args:
            buffer (str): 현재 버퍼 문자열.

        Returns:
            bool: 버퍼 길이가 max_token_length 이상이면 True, 아니면 False.

        Note:
            실제 토큰 수 카운팅 함수로 대체 필요합니다.
        """
        # TODO: 실제 토큰 카운트 함수로 대체 필요
        return len(buffer) >= self.max_token_length

    def _translate_and_write(self, buffer: str):
        """
        버퍼 내용을 번역 함수에 전달하여 번역 결과를 받아 출력 파일에 추가 저장합니다.

        Args:
            buffer (str): 번역할 텍스트 버퍼.

        Raises:
            Exception: 번역 과정에서 발생하는 모든 예외를 처리하여 로그로 기록합니다.

        Logs:
            번역 결과가 비어있거나 문자열이 아닐 경우 경고 로그를 기록합니다.
            번역 실패 시 에러 로그를 기록합니다.
        """
        try:
            translated = self.translator(buffer.strip())
            if isinstance(translated, str) and translated.strip() != "":
                self._append_to_file(translated)
            else:
                logging.warning(f"번역 결과가 비어있거나 문자열이 아님: {translated!r}")
        except Exception as e:
            logging.error(f"번역 실패: {e}")

    def _append_to_file(self, text: str):
        """
        번역된 텍스트를 출력 파일에 추가로 기록합니다.

        Args:
            text (str): 출력 파일에 추가할 번역 텍스트.

        Raises:
            IOError: 파일 쓰기 중 에러가 발생할 수 있습니다.
        """
        with open(self.output_file, 'a', encoding='utf-8') as f:
            f.write(text + "\n\n")





# Wang, X., Liu, M., Leung, A. Y., Jin, X., Dai, H., & Shang, S. (2024). Nurses’ job embeddedness and turnover intention_A systematic review and meta-analysis. International Journal of Nursing Sciences. (1)
