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

    def __init__(
        self,
        input_file: str,
        output_file: str,
        config: TranslationConfig,
        min_tokens: int = 4000,
        polling_interval: float = 2.0,
    ) -> None:
        """
        Initialize orchestrator.

        Args:
            input_file: Path to input text file
            output_file: Path to output translated file
            config: TranslationConfig instance
            min_tokens: Minimum tokens before triggering translation
            polling_interval: Seconds between file polls

        Raises:
            FileNotFoundError: If input_file doesn't exist
        """
        self.input_file = Path(input_file)
        self.output_file = Path(output_file)
        self.config = config
        self.min_tokens = min_tokens
        self.polling_interval = polling_interval

        # Components
        self.token_counter = TokenCounter()
        self.result_queue: queue.Queue[TranslationResult] = queue.Queue(maxsize=10)

        # Metrics
        self._metrics_lock = threading.Lock()
        self._total_successes = 0
        self._total_failures = 0
        self._start_time = 0.0

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
            worker.translate_async(content, offset)

        # Create and start FileWatcher
        self._file_watcher = FileWatcher(
            file_path=str(self.input_file),
            min_tokens=self.min_tokens,
            polling_interval=self.polling_interval,
            translation_callback=translation_callback,
            token_counter=self.token_counter,
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
            "Concurrent translation completed: " "%d successes, %d failures, %.2fs",
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

        Updates metrics and writes to output file.

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
