# GENERATED FROM SPEC-CONCURRENT-TRANSLATION-001
# Trace: SPEC-CONCURRENT-TRANSLATION-001

"""
Asynchronous translation worker for concurrent processing.

Executes translations in background threads without blocking file monitoring.
Results are pushed to thread-safe queue for collection by orchestrator.
"""

import logging
import queue
import threading
import time
from dataclasses import dataclass

from src.core.streaming_translator import (
    PermanentTranslationError,
    StreamingTranslator,
    TransientTranslationError,
)

logger = logging.getLogger(__name__)


@dataclass
class TranslationResult:
    """
    Result of a translation operation.

    Includes metrics, translated text, and original offset for tracking.
    """

    successes: int
    failures: int
    duration_seconds: float
    translated_text: str | None
    start_offset: int
    error: Exception | None = None


class TranslationWorker:
    """
    Execute translations asynchronously without blocking caller.

    Each translate_async() call spawns a new thread that uses
    StreamingTranslator to process content. Results are pushed to
    result_queue when complete.
    """

    def __init__(
        self,
        translator: StreamingTranslator,
        result_queue: queue.Queue[TranslationResult],
    ) -> None:
        """
        Initialize TranslationWorker.

        Args:
            translator: StreamingTranslator instance to use
            result_queue: Thread-safe queue for results
        """
        self.translator = translator
        self.result_queue = result_queue

        logger.info("TranslationWorker initialized")

    def translate_async(self, content: str, offset: int) -> None:
        """
        Start translation in background thread.

        Non-blocking; returns immediately after spawning thread.
        Result will be pushed to result_queue when complete.

        Args:
            content: Text content to translate
            offset: Starting byte offset in source file
        """
        thread = threading.Thread(
            target=self._translate_worker,
            args=(content, offset),
            name=f"TranslationWorker-{offset}",
            daemon=False,  # Must complete before exit
        )
        thread.start()
        logger.debug("Translation thread started for offset %d", offset)

    def _translate_worker(self, content: str, start_offset: int) -> None:
        """
        Worker thread that executes translation.

        Catches all exceptions and pushes result to queue.
        Never raises exceptions to caller.

        Args:
            content: Text to translate
            start_offset: Original offset for tracking
        """
        start_time = time.time()
        logger.info("Translation started for offset %d", start_offset)

        try:
            # Split content into lines for chunking
            lines = content.splitlines(keepends=True)
            if not lines:
                lines = [content]

            # Generate chunks
            chunks = list(self.translator.chunk_generator(lines))

            if not chunks:
                # No chunks to translate
                duration = time.time() - start_time
                result = TranslationResult(
                    successes=0,
                    failures=0,
                    duration_seconds=duration,
                    translated_text="",
                    start_offset=start_offset,
                    error=None,
                )
                self.result_queue.put(result)
                return

            # Translate each chunk
            translated_parts = []
            successes = 0
            failures = 0

            for chunk_index, chunk_text in chunks:
                try:
                    translated = self.translator._invoke_model(chunk_index, chunk_text)
                    translated_parts.append(translated)
                    successes += 1
                except (TransientTranslationError, PermanentTranslationError):
                    logger.exception("Chunk %d failed", chunk_index)
                    failures += 1
                    # Continue with next chunk

            # Combine translated parts
            translated_text = "\n\n".join(translated_parts) if translated_parts else ""

            duration = time.time() - start_time

            result = TranslationResult(
                successes=successes,
                failures=failures,
                duration_seconds=duration,
                translated_text=translated_text,
                start_offset=start_offset,
                error=None,
            )

            self.result_queue.put(result)
            logger.info(
                "Translation completed for offset %d: "
                "%d successes, %d failures, %.2fs",
                start_offset,
                successes,
                failures,
                duration,
            )

        except (TransientTranslationError, PermanentTranslationError) as e:
            duration = time.time() - start_time
            logger.exception("Translation failed for offset %d", start_offset)

            result = TranslationResult(
                successes=0,
                failures=1,
                duration_seconds=duration,
                translated_text=None,
                start_offset=start_offset,
                error=e,
            )
            self.result_queue.put(result)

        except Exception as e:
            duration = time.time() - start_time
            logger.exception(
                "Unexpected error in translation worker for offset %d", start_offset
            )

            result = TranslationResult(
                successes=0,
                failures=1,
                duration_seconds=duration,
                translated_text=None,
                start_offset=start_offset,
                error=e,
            )
            self.result_queue.put(result)
