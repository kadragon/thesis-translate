# GENERATED FROM SPEC-CONCURRENT-TRANSLATION-001
# Trace: SPEC-CONCURRENT-TRANSLATION-001

"""
Orchestrator for concurrent text collection and translation.

Coordinates FileWatcher and TranslationWorker to enable parallel
text collection and translation. Aggregates metrics and manages
graceful shutdown.
"""

import logging
import queue
import threading
import time
from pathlib import Path

from src.core.file_watcher import FileWatcher
from src.core.streaming_translator import StreamingTranslator, TranslationRunResult
from src.core.translation_config import TranslationConfig
from src.core.translation_worker import TranslationResult, TranslationWorker
from src.utils.token_counter import TokenCounter

logger = logging.getLogger(__name__)


class ConcurrentTranslationOrchestrator:
    """
    Coordinate FileWatcher and TranslationWorker for concurrent translation.

    Main entry point for concurrent mode. Manages lifecycle of monitoring
    and translation threads, aggregates metrics, and handles shutdown.
    """

    def __init__(  # noqa: PLR0913
        self,
        input_file: str,
        output_file: str,
        config: TranslationConfig,
        min_tokens: int = 4000,
        polling_interval: float = 2.0,
        auto_translate: bool = True,
    ) -> None:
        """
        Initialize orchestrator.

        Args:
            input_file: Path to input text file
            output_file: Path to output translated file
            config: TranslationConfig instance
            min_tokens: Minimum tokens before triggering translation
            polling_interval: Seconds between file polls
            auto_translate: If True, auto-trigger translation; If False,
                user-prompted mode (SPEC-USER-PROMPTED-001)

        Raises:
            FileNotFoundError: If input_file doesn't exist
        """
        self.input_file = Path(input_file)
        self.output_file = Path(output_file)
        self.config = config
        self.min_tokens = min_tokens
        self.polling_interval = polling_interval
        self.auto_translate = auto_translate

        # Components
        self.token_counter = TokenCounter()
        self.result_queue: queue.Queue[TranslationResult] = queue.Queue(maxsize=10)

        # Metrics
        self._metrics_lock = threading.Lock()
        self._total_successes = 0
        self._total_failures = 0
        self._start_time = 0.0

        # Active translation tracking (SPEC-USER-PROMPTED-001)
        self._active_translations = 0
        self._active_translations_lock = threading.Lock()

        # Shutdown coordination
        self._shutdown_requested = False
        self._file_watcher: FileWatcher | None = None

        logger.info(
            "ConcurrentTranslationOrchestrator initialized: "
            "input=%s, output=%s, min_tokens=%d, polling=%.1fs",
            input_file,
            output_file,
            min_tokens,
            polling_interval,
        )

    def run(self) -> TranslationRunResult:
        """
        Main entry point for concurrent translation.

        Starts FileWatcher and processes results until shutdown.
        Blocks until shutdown signal received.

        Returns:
            Aggregated TranslationRunResult

        Raises:
            FileNotFoundError: If input_file doesn't exist
        """
        if not self.input_file.exists():
            msg = f"Input file not found: {self.input_file}"
            raise FileNotFoundError(msg)

        self._start_time = time.time()
        logger.info("Starting concurrent translation")

        # Create StreamingTranslator for workers
        base_translator = StreamingTranslator(
            input_file=str(self.input_file),
            output_file=str(self.output_file),
        )

        # Create translation worker
        worker = TranslationWorker(
            translator=base_translator, result_queue=self.result_queue
        )

        # Define callback for FileWatcher
        def translation_callback(content: str, offset: int) -> None:
            logger.info("Translation triggered for offset %d", offset)
            # Increment active translation counter
            with self._active_translations_lock:
                self._active_translations += 1
            worker.translate_async(content, offset)

        # Create and start FileWatcher
        self._file_watcher = FileWatcher(
            file_path=str(self.input_file),
            min_tokens=self.min_tokens,
            polling_interval=self.polling_interval,
            translation_callback=translation_callback,
            token_counter=self.token_counter,
            auto_translate=self.auto_translate,
        )

        self._file_watcher.start()

        # Process results until shutdown
        try:
            self._process_results()
        finally:
            # Stop file watcher
            if self._file_watcher:
                self._file_watcher.stop()

        # Calculate final metrics
        duration = time.time() - self._start_time

        with self._metrics_lock:
            final_metrics = TranslationRunResult(
                successes=self._total_successes,
                failures=self._total_failures,
                duration_seconds=duration,
            )

        logger.info(
            "Concurrent translation completed: %d successes, %d failures, %.2fs",
            final_metrics.successes,
            final_metrics.failures,
            duration,
        )

        return final_metrics

    def stop(self) -> None:
        """
        Signal graceful shutdown.

        Sets shutdown flag and stops FileWatcher.
        Idempotent; safe to call multiple times.
        """
        logger.info("Shutdown signal received")
        self._shutdown_requested = True

        if self._file_watcher:
            self._file_watcher.stop()

    def get_metrics(self) -> TranslationRunResult:
        """
        Get current metrics snapshot.

        Thread-safe; can be called during run() for progress updates.

        Returns:
            Current TranslationRunResult
        """
        with self._metrics_lock:
            duration = time.time() - self._start_time if self._start_time > 0 else 0.0
            return TranslationRunResult(
                successes=self._total_successes,
                failures=self._total_failures,
                duration_seconds=duration,
            )

    def is_translation_ready(self) -> tuple[bool, int]:
        """
        Check if translation is ready to be triggered by user.

        Proxy to FileWatcher.is_translation_ready().

        Returns:
            Tuple of (ready: bool, token_count: int)
        """
        if self._file_watcher:
            return self._file_watcher.is_translation_ready()
        return (False, 0)

    def trigger_translation_manual(self) -> bool:
        """
        Manually start translation.

        Prevents concurrent translations by checking if one is already in
        progress. Calls FileWatcher.trigger_translation_manual() which triggers
        the translation callback and advances the threshold.

        Returns:
            bool: True if started, False if not ready or already translating
        """
        if self.is_translating():
            logger.warning("Translation is already in progress. Cannot start another.")
            return False

        if self._file_watcher:
            return self._file_watcher.trigger_translation_manual()
        return False

    def is_translating(self) -> bool:
        """
        Check if translation is currently in progress.

        Uses an atomic counter to track active translations, preventing
        race conditions where translations are in progress but results
        have not yet been queued.

        Returns:
            bool: True if translation worker is active
        """
        with self._active_translations_lock:
            return self._active_translations > 0

    def get_current_threshold(self) -> int:
        """
        Get the current threshold value.

        Proxy to FileWatcher.get_current_threshold().

        Returns:
            int: Current threshold (40000, 80000, 120000, etc.)
        """
        if self._file_watcher:
            return self._file_watcher.get_current_threshold()
        return self.min_tokens

    def _process_results(self) -> None:
        """
        Process translation results from queue.

        Runs until shutdown requested, then drains remaining results
        to prevent data loss from in-flight translations.
        """
        logger.debug("Result processing started")

        # Process results during normal operation
        while not self._shutdown_requested:
            try:
                # Wait for result with timeout
                result = self.result_queue.get(timeout=1.0)
                self._handle_result(result)
            except queue.Empty:
                # No result available; continue waiting
                continue

        # Drain remaining results after shutdown signal
        logger.info("Shutdown requested, draining final results from queue")
        while True:
            try:
                result = self.result_queue.get_nowait()
                self._handle_result(result)
            except queue.Empty:
                break

        logger.debug("Result processing stopped")

    def _handle_result(self, result: TranslationResult) -> None:
        """
        Handle a single translation result.

        Updates metrics, writes to output file, and updates offset after
        successful translation completion.

        Args:
            result: TranslationResult from worker thread
        """
        # Update metrics
        with self._metrics_lock:
            self._total_successes += result.successes
            self._total_failures += result.failures

        # Write translated text to output file
        if result.translated_text:
            with self.output_file.open("a", encoding="utf-8") as f:
                f.write(result.translated_text)
                f.write("\n\n")  # Separator between chunks

            logger.info(
                "Wrote translated chunk from offset %d (%d chars)",
                result.start_offset,
                len(result.translated_text),
            )

            # Update offset after successful translation
            # This ensures offset is only advanced after translation completes
            # preventing data loss on app crash during translation
            if result.successes > 0 and self._file_watcher:
                new_offset = result.start_offset + result.content_length_bytes
                self._file_watcher.update_offset_after_completion(new_offset)

        # Decrement active translation counter
        with self._active_translations_lock:
            self._active_translations -= 1
