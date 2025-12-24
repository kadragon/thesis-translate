"""Translation module for academic papers using OpenAI Chat Completions API."""
# GENERATED FROM SPEC-TRANSLATION-001
# MODIFIED FOR SPEC-PARALLEL-CHUNKS-001

from __future__ import annotations

import logging
import math
import time
from collections.abc import Iterator as TypingIterator
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
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

    def __init__(  # noqa: PLR0913
        self,
        input_file: str,
        output_file: str = config.OUTPUT_FILE,
        max_token_length: int = config.MAX_TOKEN_LENGTH,
        max_retries: int = config.TRANSLATION_MAX_RETRIES,
        retry_backoff_seconds: float = config.TRANSLATION_RETRY_BACKOFF_SECONDS,
        max_workers: int = config.TRANSLATION_MAX_WORKERS,
    ) -> None:
        """Initialize translator dependencies and configuration."""
        self.client: OpenAI = OpenAI()
        self.input_file: str = input_file
        self.output_file: str = output_file
        self.max_token_length: int = max_token_length
        self.max_retries: int = max(0, max_retries)
        self.retry_backoff_seconds: float = max(0.0, retry_backoff_seconds)
        self.max_workers: int = max(1, min(10, max_workers))  # Clamp between 1 and 10
        self.config: TranslationConfig = TranslationConfig()
        self.token_counter: TokenCounter = TokenCounter()

    # Trace: SPEC-TRANSLATION-001, TEST-TRANSLATION-001-AC2
    # Trace: SPEC-BALANCED-CHUNKS-001, AC-1, AC-2, AC-3, AC-4, AC-5, AC-6, AC-7
    def chunk_generator(self, lines: list[str]) -> ChunkIterator[tuple[int, str]]:
        """Yield chunks using balanced distribution for parallel efficiency.

        Phase 1: Calculate total tokens across all lines
        Phase 2: Calculate num_chunks and target_chunk_size
        Phase 3: Distribute lines evenly across chunks
        """

        # Phase 1: Calculate total tokens and individual line tokens
        line_tokens = [self.token_counter.count_tokens(line) for line in lines]
        total_tokens = sum(line_tokens)

        # Phase 2: Calculate target distribution
        if total_tokens <= self.max_token_length:
            # AC-7: Single chunk case
            all_lines = "".join(lines)
            logger.info("chunk=1 boundary len=%d", len(all_lines))
            yield 1, all_lines
            return

        num_chunks = math.ceil(total_tokens / self.max_token_length)
        target_chunk_size = total_tokens / num_chunks

        # Phase 3: Distribute lines into balanced chunks
        buffer = ""
        current_chunk_tokens = 0
        chunk_index = 0

        for i, line in enumerate(lines):
            line_token_count = line_tokens[i]

            # Handle oversized single line (AC-6)
            if not buffer and line_token_count > self.max_token_length:
                chunk_index += 1
                logger.warning(
                    "chunk=%d single line over limit len=%d",
                    chunk_index,
                    len(line),
                )
                yield chunk_index, line
                continue

            # Check if adding this line would exceed target (and we have content)
            candidate_tokens = current_chunk_tokens + line_token_count

            # Finalize chunk if:
            # 1. We have content in buffer AND
            # 2. We've reached/exceeded target OR would exceed it significantly
            if buffer and candidate_tokens >= target_chunk_size:
                # Only finalize if not on last chunk or significantly exceeding
                chunks_remaining = num_chunks - chunk_index
                should_finalize = (
                    chunks_remaining > 1 or candidate_tokens > self.max_token_length
                )
                if should_finalize:
                    chunk_index += 1
                    logger.info("chunk=%d boundary len=%d", chunk_index, len(buffer))
                    yield chunk_index, buffer

                    # Check if the next line is oversized before buffering
                    if line_token_count > self.max_token_length:
                        chunk_index += 1
                        logger.warning(
                            "chunk=%d single line over limit len=%d",
                            chunk_index,
                            len(line),
                        )
                        yield chunk_index, line
                        buffer = ""
                        current_chunk_tokens = 0
                    else:
                        buffer = line
                        current_chunk_tokens = line_token_count
                else:
                    # Last chunk, accumulate remaining lines
                    buffer += line
                    current_chunk_tokens = candidate_tokens
            else:
                # Accumulate line
                buffer += line
                current_chunk_tokens = candidate_tokens

        # Yield final buffer if any content remains
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

        return None  # pragma: no cover

    # Trace: SPEC-TRANSLATION-001, TEST-TRANSLATION-001-AC1
    # Trace: SPEC-TRANSLATION-001, TEST-TRANSLATION-001-AC7
    # Trace: SPEC-TRANSLATION-001, TEST-TRANSLATION-001-AC9
    # Trace: SPEC-TRANSLATION-001, TEST-TRANSLATION-001-AC10
    # Trace: SPEC-REFACTOR-DRY-001, AC-1, AC-2
    # Trace: SPEC-PARALLEL-CHUNKS-001, AC-1, AC-2, AC-3, AC-4, AC-5, AC-6, AC-7
    def translate(self) -> TranslationRunResult:
        """Translate the input file and write results while tracking metrics.

        Uses parallel processing when max_workers > 1, sequential when max_workers == 1.
        Results are written in original chunk order regardless of completion order.
        """
        start_time = time.perf_counter()

        try:
            with Path(self.input_file).open(encoding="utf-8") as file:
                lines = file.readlines()
        except FileNotFoundError:
            logger.exception("입력 파일을 찾을 수 없습니다: %s", self.input_file)
            raise

        # Materialize chunks for progress tracking
        chunks = list(self.chunk_generator(lines))
        total_chunks = len(chunks)
        logger.info(
            "총 %d개의 번역 청크를 처리합니다 (max_workers=%d).",
            total_chunks,
            self.max_workers,
        )

        if self.max_workers == 1:
            # Sequential mode (backward compatible)
            result = self._translate_sequential(chunks, total_chunks)
        else:
            # Parallel mode
            result = self._translate_parallel(chunks, total_chunks)

        duration = time.perf_counter() - start_time
        logger.info(
            "번역 완료: successes=%d, failures=%d, duration=%.2fs, output=%s",
            result.successes,
            result.failures,
            duration,
            self.output_file,
        )

        return TranslationRunResult(
            successes=result.successes,
            failures=result.failures,
            duration_seconds=duration,
        )

    def _translate_sequential(
        self, chunks: list[tuple[int, str]], total_chunks: int
    ) -> TranslationRunResult:
        """Sequential translation (original behavior)."""
        translated_content: list[str] = []
        successes = 0
        failures = 0

        for chunk_index, chunk_text in chunks:
            logger.info("processing chunk=%d/%d", chunk_index, total_chunks)
            translation = self._translate_chunk(chunk_index, chunk_text)
            if translation:
                translated_content.append(translation)
                successes += 1
            else:
                failures += 1

        with Path(self.output_file).open("w", encoding="utf-8") as file:
            file.writelines(content + "\n\n" for content in translated_content)

        return TranslationRunResult(
            successes=successes,
            failures=failures,
            duration_seconds=0.0,  # Duration calculated by caller
        )

    def _translate_parallel(
        self, chunks: list[tuple[int, str]], total_chunks: int
    ) -> TranslationRunResult:
        """Parallel translation using ThreadPoolExecutor.

        Chunks are processed in parallel up to max_workers limit.
        Results are collected in original chunk order.
        """
        # Dictionary to store futures and results by chunk_index
        future_to_chunk: dict[Future[str | None], int] = {}
        translated_results: dict[int, str] = {}
        successes = 0
        failures = 0

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all chunks for parallel processing
            for chunk_index, chunk_text in chunks:
                future = executor.submit(self._translate_chunk, chunk_index, chunk_text)
                future_to_chunk[future] = chunk_index
            logger.info("submitted %d chunks for translation", total_chunks)

            # Collect results as they complete
            for future in as_completed(future_to_chunk):
                chunk_index = future_to_chunk[future]
                try:
                    translation = future.result()
                    if translation:
                        translated_results[chunk_index] = translation
                        successes += 1
                        logger.info("chunk=%d completed successfully", chunk_index)
                    else:
                        failures += 1
                        logger.warning("chunk=%d failed", chunk_index)
                except Exception:
                    logger.exception("chunk=%d raised exception", chunk_index)
                    failures += 1

        # Write results in original chunk order
        translated_content = [
            translated_results[chunk_index]
            for chunk_index, _ in chunks
            if chunk_index in translated_results
        ]

        with Path(self.output_file).open("w", encoding="utf-8") as file:
            file.writelines(content + "\n\n" for content in translated_content)

        return TranslationRunResult(
            successes=successes,
            failures=failures,
            duration_seconds=0.0,  # Duration calculated by caller
        )

    # Trace: SPEC-TRANSLATION-001, TEST-TRANSLATION-001-AC8
    def format_output(self) -> None:
        """Format the output file with consistent indentation."""
        OutputFormatter.format_output(self.output_file)
