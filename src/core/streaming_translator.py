"""Translation module for academic papers using OpenAI Chat Completions API."""
# Trace: SPEC-RICH-UX-001, TASK-20251226-RICH-UX-01
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
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TaskID,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)

from src import config
from src.core.translation_config import TranslationConfig
from src.utils.output_formatter import OutputFormatter
from src.utils.rich_logging import get_console
from src.utils.token_counter import TokenCounter

logger = logging.getLogger(__name__)


class NoOpProgress:
    """No-operation progress handler for cases where progress tracking is disabled.

    This class provides a safe default for optional Progress parameters,
    allowing methods to call update() without None checks.

    Trace: SPEC-REFACTOR-VALIDATION-001, TASK-20251228-REFACTOR-VALIDATION-001
    """

    def update(
        self,
        task_id: TaskID | None = None,
        *,
        completed: float | None = None,
        total: float | None = None,
        **kwargs,
    ) -> None:
        """Silently ignore all progress updates."""

    def add_task(self, _description: str, **_kwargs) -> TaskID:
        """Return a dummy task ID."""
        return TaskID(0)


@dataclass(slots=True)
class TranslationRunResult:
    """Aggregate metrics for a translation invocation."""

    successes: int
    failures: int
    duration_seconds: float


class TranslationError(Exception):
    """Raised when an error occurs during translation.

    Args:
        is_transient: True if error is retryable, False if permanent
        message: Error message (defaults based on is_transient)
    """

    def __init__(self, is_transient: bool, message: str | None = None) -> None:
        self.is_transient = is_transient
        if message is None:
            message = (
                "OpenAI API 호출 실패"
                if is_transient
                else "응답에 번역 결과가 없습니다."
            )
        super().__init__(message)


class StreamingTranslator:
    """Translator for academic papers using OpenAI Chat Completions API."""

    # Trace: SPEC-REFACTOR-CONSTANTS-001, TASK-20251228-REFACTOR-CONSTANTS-001
    # Constants for model invocation and token estimation
    API_TIMEOUT_SECONDS = 180.0
    ESTIMATED_OUTPUT_TOKEN_RATIO = 1.3
    KOREAN_CHAR_TO_TOKEN_RATIO = 2.5
    MIN_LAST_CHUNK_RATIO = 0.7
    MIN_CHUNKS_FOR_MERGE = 2

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
    def chunk_generator(  # noqa: PLR0912, PLR0915
        self, lines: list[str]
    ) -> ChunkIterator[tuple[int, str]]:
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
        chunks: list[tuple[str, int, bool]] = []

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
                chunks.append((line, line_token_count, True))
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
                    chunks.append((buffer, current_chunk_tokens, False))

                    # Check if the next line is oversized before buffering
                    if line_token_count > self.max_token_length:
                        chunk_index += 1
                        logger.warning(
                            "chunk=%d single line over limit len=%d",
                            chunk_index,
                            len(line),
                        )
                        chunks.append((line, line_token_count, True))
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

        # Capture final buffer if any content remains
        if buffer:
            chunk_index += 1
            chunks.append((buffer, current_chunk_tokens, False))

        # Merge tiny last chunk into previous if within max_token_length
        if len(chunks) >= self.MIN_CHUNKS_FOR_MERGE:
            last_text, last_tokens, last_oversized = chunks[-1]
            prev_text, prev_tokens, prev_oversized = chunks[-2]
            if (
                not last_oversized
                and not prev_oversized
                and last_tokens < self.MIN_LAST_CHUNK_RATIO * target_chunk_size
                and prev_tokens + last_tokens <= self.max_token_length
            ):
                chunks = [
                    *chunks[:-2],
                    (prev_text + last_text, prev_tokens + last_tokens, False),
                ]

        for idx, (chunk_text, _chunk_tokens, _oversized) in enumerate(chunks, start=1):
            logger.info("chunk=%d boundary len=%d", idx, len(chunk_text))
            yield idx, chunk_text

    # Trace: SPEC-TRANSLATION-001, TEST-TRANSLATION-001-AC3
    # Trace: SPEC-REFACTOR-VALIDATION-001, TASK-20251228-REFACTOR-VALIDATION-001
    def _invoke_model(
        self,
        chunk_index: int,
        chunk_text: str,
        progress: Progress | None = None,
        task_id: TaskID | None = None,
    ) -> str:
        """Call OpenAI for a single chunk and return translated content.

        Args:
            chunk_index: Index of the chunk being translated
            chunk_text: Text content to translate
            progress: Optional progress tracker. If None, updates are skipped.
            task_id: Optional task ID for progress tracking. Only used if
                progress is not None.

        Returns:
            Translated text content

        Raises:
            TranslationError: If API call fails (transient) or response is
                empty (permanent)
        """
        # Defensive: Replace None with NoOp handler to simplify downstream code
        actual_progress: Progress | NoOpProgress
        if progress is None:
            actual_progress = NoOpProgress()
            task_id = None
        else:
            actual_progress = progress

        prompt = self.config.PROMPT_TEMPLATE.format(
            glossary=self.config.glossary,
            text=chunk_text,
        )

        # 예상 출력 토큰 수 추정 (입력 토큰 수 기반)
        input_tokens = self.token_counter.count_tokens(chunk_text)
        # 한글 번역은 보통 입력보다 1.2-1.5배 정도
        estimated_output_tokens = int(input_tokens * self.ESTIMATED_OUTPUT_TOKEN_RATIO)

        try:
            response = self.client.chat.completions.create(
                model=self.config.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=self.config.temperature,
                timeout=self.API_TIMEOUT_SECONDS,  # 3분 타임아웃 (큰 청크 처리용)
                stream=True,  # 스트리밍 활성화
            )

            # 스트리밍 응답 수집 with 진행률 표시
            content_parts: list[str] = []
            received_chars = 0

            for stream_chunk in response:
                if stream_chunk.choices[0].delta.content:
                    chunk_content = stream_chunk.choices[0].delta.content
                    content_parts.append(chunk_content)
                    received_chars += len(chunk_content)

                    # 진행률 업데이트 (프로그레스바 또는 로그)
                    # 한글 평균: 1글자 ≈ 2.5 토큰
                    estimated_tokens = int(
                        received_chars * self.KOREAN_CHAR_TO_TOKEN_RATIO
                    )
                    completed = min(estimated_tokens, estimated_output_tokens)
                    if task_id is not None:
                        actual_progress.update(
                            task_id, completed=completed, total=estimated_output_tokens
                        )

            content: str | None = "".join(content_parts) if content_parts else None

            # 완료 처리
            if content and task_id is not None:
                actual_progress.update(task_id, completed=estimated_output_tokens)
        except Exception as exc:  # pragma: no cover - exercised via mocks
            logger.exception("OpenAI API 호출 중 오류 발생 (chunk=%d)", chunk_index)
            raise TranslationError(is_transient=True) from exc

        if not content:
            raise TranslationError(is_transient=False)

        return content

    # Trace: SPEC-TRANSLATION-001, TEST-TRANSLATION-001-AC3
    # Trace: SPEC-TRANSLATION-001, TEST-TRANSLATION-001-AC4
    # Trace: SPEC-TRANSLATION-001, TEST-TRANSLATION-001-AC5
    # Trace: SPEC-TRANSLATION-001, TEST-TRANSLATION-001-AC6
    # Trace: SPEC-REFACTOR-VALIDATION-001, TASK-20251228-REFACTOR-VALIDATION-001
    def _translate_chunk(
        self,
        chunk_index: int,
        chunk_text: str,
        progress: Progress | None = None,
        task_id: TaskID | None = None,
    ) -> str | None:
        """Translate a chunk with retry/backoff logic.

        Args:
            chunk_index: Index of the chunk being translated
            chunk_text: Text content to translate
            progress: Optional progress tracker. If None, updates are skipped.
                The method is safe to call with progress=None.
            task_id: Optional task ID for progress tracking. Only used if
                progress is not None.

        Returns:
            Translated text content, or None if all retry attempts failed

        Note:
            Progress parameter is optional and can be None. When None, no progress
            updates are performed. The method delegates to _invoke_model which handles
            the None case with a NoOp progress handler internally.
        """
        # Defensive: Validate progress/task_id relationship
        # Note: _invoke_model handles None progress internally with NoOpProgress
        max_attempts = self.max_retries + 1

        for attempt in range(1, max_attempts + 1):
            try:
                translation = self._invoke_model(
                    chunk_index, chunk_text, progress, task_id
                )
            except TranslationError as exc:
                if exc.is_transient:
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

    # Trace: SPEC-REFACTOR-DEDUP-001, TASK-20251228-REFACTOR-DEDUP-001
    # Trace: TEST-REFACTOR-DEDUP-001-AC1, TEST-REFACTOR-DEDUP-001-AC2
    def _write_translations(
        self,
        results: dict[int, str],
        chunks: list[tuple[int, str]],
        output_file: str,
    ) -> None:
        """Write translated content to file with correct formatting.

        Args:
            results: Dictionary mapping chunk_index to translated content
            chunks: List of (chunk_index, chunk_text) tuples in original order
            output_file: Path to output file

        Note:
            Writes chunks in original order with double newline between chunks.
            Only writes chunks that were successfully translated (exist in results).
        """
        # Extract translated content in original chunk order
        translated_content = [
            results[chunk_index] for chunk_index, _ in chunks if chunk_index in results
        ]

        with Path(output_file).open("w", encoding="utf-8") as file:
            file.writelines(content + "\n\n" for content in translated_content)

    # Trace: SPEC-REFACTOR-DEDUP-001, TASK-20251228-REFACTOR-DEDUP-001
    # Trace: TEST-REFACTOR-DEDUP-001-AC3, TEST-REFACTOR-DEDUP-001-AC4
    def _update_task_progress(
        self,
        success: bool,
        chunk_index: int,
        progress: Progress,
        task_id: TaskID,
        reason: str = "failed",
    ) -> None:
        """Update progress bar for a completed chunk.

        Args:
            success: True if chunk translated successfully, False if failed
            chunk_index: Index of the chunk being updated
            progress: Progress tracker instance
            task_id: Task ID for the progress bar
            reason: The reason for failure, displayed in the progress bar

        Note:
            Success: Marks task as 100% complete and hides it
            Failure: Updates description to show failure and hides it
        """
        if success:
            progress.update(task_id, completed=100, visible=False)
        else:
            progress.update(
                task_id,
                description=f"[red]Chunk {chunk_index} ({reason})",
                visible=False,
            )

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

        # Create progress bar with rich
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            MofNCompleteColumn(),
            TimeElapsedColumn(),
            TimeRemainingColumn(),
            console=get_console(),
            transient=True,
        ) as progress:
            # Add overall progress task
            overall_task = progress.add_task(
                f"[cyan]Translating {total_chunks} chunks...", total=total_chunks
            )

            if self.max_workers == 1:
                # Sequential mode (backward compatible)
                result = self._translate_sequential(chunks, progress, overall_task)
            else:
                # Parallel mode
                result = self._translate_parallel(chunks, progress, overall_task)

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
        self,
        chunks: list[tuple[int, str]],
        progress: Progress,
        overall_task: TaskID,
    ) -> TranslationRunResult:
        """Sequential translation (original behavior)."""
        translated_results: dict[int, str] = {}
        successes = 0
        failures = 0

        for chunk_index, chunk_text in chunks:
            # Add individual chunk task
            chunk_task = progress.add_task(
                f"[green]Chunk {chunk_index}", total=100, start=True
            )

            translation = self._translate_chunk(
                chunk_index, chunk_text, progress, chunk_task
            )

            if translation:
                translated_results[chunk_index] = translation
                successes += 1
            else:
                failures += 1

            # Update task progress (unified method)
            self._update_task_progress(
                success=translation is not None,
                chunk_index=chunk_index,
                progress=progress,
                task_id=chunk_task,
            )

            # Update overall progress
            progress.update(overall_task, advance=1)

        # Write translations (unified method)
        self._write_translations(translated_results, chunks, self.output_file)

        return TranslationRunResult(
            successes=successes,
            failures=failures,
            duration_seconds=0.0,  # Duration calculated by caller
        )

    def _translate_parallel(
        self,
        chunks: list[tuple[int, str]],
        progress: Progress,
        overall_task: TaskID,
    ) -> TranslationRunResult:
        """Parallel translation using ThreadPoolExecutor.

        Chunks are processed in parallel up to max_workers limit.
        Results are collected in original chunk order.
        """
        # Dictionary to store futures and results by chunk_index
        future_to_chunk: dict[Future[str | None], int] = {}
        chunk_to_task: dict[int, TaskID] = {}
        translated_results: dict[int, str] = {}
        successes = 0
        failures = 0

        # Create task for each chunk
        for chunk_index, _ in chunks:
            chunk_task = progress.add_task(
                f"[green]Chunk {chunk_index}", total=100, start=True
            )
            chunk_to_task[chunk_index] = chunk_task

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all chunks for parallel processing
            for chunk_index, chunk_text in chunks:
                task_id = chunk_to_task[chunk_index]
                future = executor.submit(
                    self._translate_chunk, chunk_index, chunk_text, progress, task_id
                )
                future_to_chunk[future] = chunk_index

            # Collect results as they complete
            for future in as_completed(future_to_chunk):
                chunk_index = future_to_chunk[future]
                chunk_task = chunk_to_task[chunk_index]

                try:
                    translation = future.result()
                    if translation:
                        translated_results[chunk_index] = translation
                        successes += 1
                    else:
                        failures += 1

                    # Update task progress (unified method)
                    self._update_task_progress(
                        success=translation is not None,
                        chunk_index=chunk_index,
                        progress=progress,
                        task_id=chunk_task,
                    )
                except Exception:
                    logger.exception("chunk=%d raised exception", chunk_index)
                    failures += 1
                    # Update task progress for exception case
                    self._update_task_progress(
                        success=False,
                        chunk_index=chunk_index,
                        progress=progress,
                        task_id=chunk_task,
                        reason="error",
                    )

                # Update overall progress
                progress.update(overall_task, advance=1)

        # Write translations (unified method)
        self._write_translations(translated_results, chunks, self.output_file)

        return TranslationRunResult(
            successes=successes,
            failures=failures,
            duration_seconds=0.0,  # Duration calculated by caller
        )

    # Trace: SPEC-TRANSLATION-001, TEST-TRANSLATION-001-AC8
    def format_output(self) -> None:
        """Format the output file with consistent indentation."""
        OutputFormatter.format_output(self.output_file)
