"""Translation module for academic papers using OpenAI Chat Completions API."""
# GENERATED FROM SPEC-TRANSLATION-001

from __future__ import annotations

import logging
import time
from collections.abc import Iterator as TypingIterator
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator as ChunkIterator
else:  # pragma: no cover - alias for runtime type hints
    ChunkIterator = TypingIterator

from openai import OpenAI

from src import config
from src.core.translation_config import TranslationConfig
from src.utils.output_formatter import OutputFormatter
from src.utils.token_counter import TokenCounter

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class TranslationRunResult:
    """Aggregate metrics for a translation invocation."""

    successes: int
    failures: int
    duration_seconds: float


class TransientTranslationError(Exception):
    """Raised when a retryable error occurs during translation."""

    def __init__(self, message: str = "OpenAI API 호출 실패") -> None:
        super().__init__(message)


class PermanentTranslationError(Exception):
    """Raised when a non-retryable error occurs during translation."""

    def __init__(self, message: str = "응답에 번역 결과가 없습니다.") -> None:
        super().__init__(message)


class StreamingTranslator:
    """Translator for academic papers using OpenAI Chat Completions API."""

    def __init__(
        self,
        input_file: str,
        output_file: str = config.OUTPUT_FILE,
        max_token_length: int = config.MAX_TOKEN_LENGTH,
        max_retries: int = config.TRANSLATION_MAX_RETRIES,
        retry_backoff_seconds: float = config.TRANSLATION_RETRY_BACKOFF_SECONDS,
    ) -> None:
        """Initialize translator dependencies and configuration."""
        self.client: OpenAI = OpenAI()
        self.input_file: str = input_file
        self.output_file: str = output_file
        self.max_token_length: int = max_token_length
        self.max_retries: int = max(0, max_retries)
        self.retry_backoff_seconds: float = max(0.0, retry_backoff_seconds)
        self.config: TranslationConfig = TranslationConfig()
        self.token_counter: TokenCounter = TokenCounter()

    # Trace: SPEC-TRANSLATION-001, TEST-TRANSLATION-001-AC2
    def chunk_generator(self, lines: list[str]) -> ChunkIterator[tuple[int, str]]:
        """Yield chunk indices and text while respecting the token limit."""
        buffer = ""
        chunk_index = 0

        for line in lines:
            candidate = buffer + line if buffer else line
            token_count = self.token_counter.count_tokens(candidate)

            if buffer and token_count > self.max_token_length:
                chunk_index += 1
                logger.info("chunk=%d boundary len=%d", chunk_index, len(buffer))
                yield chunk_index, buffer
                buffer = line
            elif not buffer and token_count > self.max_token_length:
                chunk_index += 1
                logger.warning(
                    "chunk=%d single line over limit len=%d",
                    chunk_index,
                    len(candidate),
                )
                yield chunk_index, candidate
                buffer = ""
            else:
                buffer = candidate

        if buffer:
            chunk_index += 1
            logger.info("chunk=%d boundary len=%d", chunk_index, len(buffer))
            yield chunk_index, buffer

    # Trace: SPEC-TRANSLATION-001, TEST-TRANSLATION-001-AC3
    def _invoke_model(self, chunk_index: int, chunk_text: str) -> str:
        """Call OpenAI for a single chunk and return translated content."""
        prompt = self.config.PROMPT_TEMPLATE.format(
            glossary=self.config.glossary,
            text=chunk_text,
        )

        try:
            response = self.client.chat.completions.create(
                model=self.config.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=self.config.temperature,
            )
            content = response.choices[0].message.content
        except Exception as exc:  # pragma: no cover - exercised via mocks
            logger.exception("OpenAI API 호출 중 오류 발생 (chunk=%d)", chunk_index)
            raise TransientTranslationError from exc

        if not content:
            raise PermanentTranslationError

        return str(content)

    # Trace: SPEC-TRANSLATION-001, TEST-TRANSLATION-001-AC3
    # Trace: SPEC-TRANSLATION-001, TEST-TRANSLATION-001-AC4
    # Trace: SPEC-TRANSLATION-001, TEST-TRANSLATION-001-AC5
    # Trace: SPEC-TRANSLATION-001, TEST-TRANSLATION-001-AC6
    def _translate_chunk(self, chunk_index: int, chunk_text: str) -> str | None:
        """Translate a chunk with retry/backoff logic."""
        max_attempts = self.max_retries + 1

        for attempt in range(1, max_attempts + 1):
            try:
                translation = self._invoke_model(chunk_index, chunk_text)
            except TransientTranslationError as exc:
                logger.warning(
                    "chunk=%d retry attempt=%d/%d: %s",
                    chunk_index,
                    attempt,
                    max_attempts,
                    exc,
                )
                if attempt == max_attempts:
                    logger.exception("chunk=%d retry limit exceeded", chunk_index)
                    return None
                if self.retry_backoff_seconds > 0:
                    time.sleep(self.retry_backoff_seconds)
                continue
            except PermanentTranslationError:
                logger.exception("chunk=%d permanent failure", chunk_index)
                return None
            else:
                logger.info(
                    "chunk=%d translation ok attempt=%d/%d",
                    chunk_index,
                    attempt,
                    max_attempts,
                )
                return translation

        return None

    # Trace: SPEC-TRANSLATION-001, TEST-TRANSLATION-001-AC1
    # Trace: SPEC-TRANSLATION-001, TEST-TRANSLATION-001-AC7
    # Trace: SPEC-TRANSLATION-001, TEST-TRANSLATION-001-AC9
    # Trace: SPEC-TRANSLATION-001, TEST-TRANSLATION-001-AC10
    def translate(self) -> TranslationRunResult:
        """Translate the input file and write results while tracking metrics."""
        start_time = time.perf_counter()

        try:
            with Path(self.input_file).open(encoding="utf-8") as file:
                lines = file.readlines()
        except FileNotFoundError:
            logger.exception("입력 파일을 찾을 수 없습니다: %s", self.input_file)
            raise

        total_chunks = self._calculate_total_chunks(lines)
        logger.info("총 %d개의 번역 청크를 처리합니다.", total_chunks)

        translated_content: list[str] = []
        successes = 0
        failures = 0

        for chunk_index, chunk_text in self.chunk_generator(lines):
            logger.info("processing chunk=%d/%d", chunk_index, total_chunks)
            translation = self._translate_chunk(chunk_index, chunk_text)
            if translation:
                translated_content.append(translation)
                successes += 1
            else:
                failures += 1

        with Path(self.output_file).open("w", encoding="utf-8") as file:
            file.writelines(content + "\n\n" for content in translated_content)

        duration = time.perf_counter() - start_time
        logger.info(
            "번역 완료: successes=%d, failures=%d, duration=%.2fs, output=%s",
            successes,
            failures,
            duration,
            self.output_file,
        )

        return TranslationRunResult(
            successes=successes,
            failures=failures,
            duration_seconds=duration,
        )

    # Trace: SPEC-TRANSLATION-001, TEST-TRANSLATION-001-AC8
    def format_output(self) -> None:
        """Format the output file with consistent indentation."""
        OutputFormatter.format_output(self.output_file)

    def _calculate_total_chunks(self, lines: list[str]) -> int:
        """Determine total chunk count without materialising chunk texts."""
        buffer = ""
        total = 0

        for line in lines:
            candidate = buffer + line if buffer else line
            token_count = self.token_counter.count_tokens(candidate)

            if buffer and token_count > self.max_token_length:
                total += 1
                buffer = line
            elif not buffer and token_count > self.max_token_length:
                total += 1
                buffer = ""
            else:
                buffer = candidate

        if buffer:
            total += 1

        return total
