import logging
import os
import time
from pathlib import Path

import tiktoken
from openai import OpenAI

from src import config
from src.core.translation_config import TranslationConfig

logger = logging.getLogger(__name__)


class NormalTranslator:
    def __init__(
        self,
        input_file: str,
        output_file: str = config.OUTPUT_FILE,
        max_token_length: int = config.MAX_TOKEN_LENGTH,
    ):
        self.client = OpenAI()
        self.input_file = input_file
        self.output_file = output_file
        self.max_token_length = max_token_length
        self.config = TranslationConfig()
        self.encoding = tiktoken.get_encoding("cl100k_base")

    def _count_tokens(self, text: str) -> int:
        return len(self.encoding.encode(text))

    def _translate_chunk(self, text: str) -> str:
        prompt = self.config.PROMPT_TEMPLATE.format(
            glossary=self.config.glossary, text=text
        )
        try:
            response = self.client.chat.completions.create(
                model=self.config.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=self.config.temperature,
            )
            return str(response.choices[0].message.content or "")
        except Exception as e:
            logger.exception(f"OpenAI API 호출 중 오류 발생: {e}")
            return ""

    def translate(self):
        try:
            with Path(self.input_file).open(encoding="utf-8") as f:
                lines = f.readlines()
        except FileNotFoundError:
            logger.exception(f"입력 파일을 찾을 수 없습니다: {self.input_file}")
            raise

        # Calculate total chunks
        total_chunks = 0
        temp_buffer = ""
        for line in lines:
            if self._count_tokens(temp_buffer + line) > self.max_token_length:
                if temp_buffer:
                    total_chunks += 1
                temp_buffer = ""
            temp_buffer += line
        if temp_buffer:
            total_chunks += 1

        logger.info(f"총 {total_chunks}개의 번역 청크를 처리합니다.")

        buffer = ""
        translated_content = []
        current_chunk = 0
        for line in lines:
            if self._count_tokens(buffer + line) > self.max_token_length:
                if buffer:
                    current_chunk += 1
                    logger.info(f"번역 청크 {current_chunk}/{total_chunks} 처리 중...")
                    translated_text = self._translate_chunk(buffer)
                    if translated_text:
                        translated_content.append(translated_text)
                buffer = ""
            buffer += line

        if buffer:
            current_chunk += 1
            logger.info(f"번역 청크 {current_chunk}/{total_chunks} 처리 중...")
            translated_text = self._translate_chunk(buffer)
            if translated_text:
                translated_content.append(translated_text)

        with Path(self.output_file).open("w", encoding="utf-8") as f:
            f.writelines(content + "\n\n" for content in translated_content)

        logger.info(
            f"번역이 완료되었습니다. 결과가 {self.output_file}에 저장되었습니다."
        )

    def format_output(self):
        with Path(self.output_file).open(encoding="utf-8") as f:
            lines = f.readlines()

        new_lines = []
        for line in lines:
            stripped = line.rstrip("\n")
            if stripped.strip() == "":
                new_lines.append(line)
            elif not stripped.startswith("  "):
                new_lines.append("  " + stripped + "\n")
            else:
                new_lines.append(line)

        with Path(self.output_file).open("w", encoding="utf-8") as f:
            f.writelines(new_lines)
