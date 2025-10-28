"""Translation module for academic papers using OpenAI Chat Completions API."""

import logging
from pathlib import Path

from openai import OpenAI

from src import config
from src.core.translation_config import TranslationConfig
from src.utils.output_formatter import OutputFormatter
from src.utils.token_counter import TokenCounter

logger = logging.getLogger(__name__)


class StreamingTranslator:
    """Translator for academic papers using OpenAI Chat Completions API.

    Handles text chunking, API calls, and output formatting for paper translation.
    """

    def __init__(
        self,
        input_file: str,
        output_file: str = config.OUTPUT_FILE,
        max_token_length: int = config.MAX_TOKEN_LENGTH,
    ) -> None:
        """Initialize the translator.

        Args:
            input_file: Path to the input text file.
            output_file: Path to output translation file (default: from config).
            max_token_length: Max tokens per translation chunk (default: config).
        """
        self.client: OpenAI = OpenAI()
        self.input_file: str = input_file
        self.output_file: str = output_file
        self.max_token_length: int = max_token_length
        self.config: TranslationConfig = TranslationConfig()
        self.token_counter: TokenCounter = TokenCounter()

    def _translate_chunk(self, text: str) -> str:
        """Translate a single chunk of text using OpenAI API.

        Args:
            text: Text chunk to translate.

        Returns:
            Translated text, or empty string if API call fails.
        """
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
        except Exception:
            logger.exception("OpenAI API 호출 중 오류 발생")
            return ""

    def translate(self) -> None:
        """Translate the input file and save results to output file.

        The text is chunked based on token count to respect API limits.

        Raises:
            FileNotFoundError: If input file does not exist.
        """
        try:
            with Path(self.input_file).open(encoding="utf-8") as f:
                lines = f.readlines()
        except FileNotFoundError:
            logger.exception("입력 파일을 찾을 수 없습니다: %s", self.input_file)
            raise

        # Calculate total chunks
        total_chunks = 0
        temp_buffer = ""
        for line in lines:
            if (
                self.token_counter.count_tokens(temp_buffer + line)
                > self.max_token_length
            ):
                if temp_buffer:
                    total_chunks += 1
                temp_buffer = ""
            temp_buffer += line
        if temp_buffer:
            total_chunks += 1

        logger.info("총 %d개의 번역 청크를 처리합니다.", total_chunks)

        # Translate chunks
        buffer = ""
        translated_content: list[str] = []
        current_chunk = 0
        for line in lines:
            if self.token_counter.count_tokens(buffer + line) > self.max_token_length:
                if buffer:
                    current_chunk += 1
                    logger.info(
                        "번역 청크 %d/%d 처리 중...", current_chunk, total_chunks
                    )
                    translated_text = self._translate_chunk(buffer)
                    if translated_text:
                        translated_content.append(translated_text)
                buffer = ""
            buffer += line

        if buffer:
            current_chunk += 1
            logger.info("번역 청크 %d/%d 처리 중...", current_chunk, total_chunks)
            translated_text = self._translate_chunk(buffer)
            if translated_text:
                translated_content.append(translated_text)

        # Write output
        with Path(self.output_file).open("w", encoding="utf-8") as f:
            f.writelines(content + "\n\n" for content in translated_content)

        logger.info(
            "번역이 완료되었습니다. 결과가 %s에 저장되었습니다.", self.output_file
        )

    def format_output(self) -> None:
        """Format the output file with consistent indentation."""
        OutputFormatter.format_output(self.output_file)
