# GENERATED FROM SPEC-CONCURRENT-TRANSLATION-001
# Trace: SPEC-CONCURRENT-TRANSLATION-001

"""
File monitoring system for concurrent translation.

Monitors input file for changes and triggers translation when threshold exceeded.
Uses polling-based approach with configurable interval.
"""

import json
import logging
import threading
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from src.utils.token_counter import TokenCounter

logger = logging.getLogger(__name__)


class FileWatcherError(Exception):
    """Raised when FileWatcher encounters unrecoverable error."""


class FileWatcher:
    """
    Monitor file for changes and trigger translation callback.

    Uses polling to detect new content. When accumulated tokens exceed
    threshold, triggers callback with untranslated content.

    Thread-safe: uses locks for offset updates and state persistence.
    """

    def __init__(  # noqa: PLR0913
        self,
        file_path: str,
        min_tokens: int,
        polling_interval: float,
        translation_callback: Callable[[str, int], None],
        token_counter: TokenCounter,
        state_file: str = ".translation_state.json",
    ) -> None:
        """
        Initialize FileWatcher.

        Args:
            file_path: Path to file to monitor
            min_tokens: Minimum tokens before triggering translation
            polling_interval: Seconds between polls (min 0.5)
            translation_callback: Function to call with (content, offset)
            token_counter: TokenCounter instance for counting tokens
            state_file: Path to state persistence file

        Raises:
            FileWatcherError: If file_path doesn't exist or invalid params
        """
        self.file_path = Path(file_path)
        self.min_tokens = min_tokens
        self.polling_interval = max(polling_interval, 0.5)
        self.translation_callback = translation_callback
        self.token_counter = token_counter
        self.state_file = Path(state_file)

        # Thread coordination
        self._monitoring_thread: threading.Thread | None = None
        self._shutdown_event = threading.Event()
        self._offset_lock = threading.Lock()

        # State
        self._last_processed_offset = 0

        # Load state from disk
        self._load_state()

        logger.info(
            "FileWatcher initialized: file=%s, "
            "min_tokens=%d, interval=%.1fs, resume_offset=%d",
            file_path,
            min_tokens,
            polling_interval,
            self._last_processed_offset,
        )

    def start(self) -> None:
        """
        Start monitoring thread.

        Non-blocking; returns immediately after spawning daemon thread.

        Raises:
            FileWatcherError: If file doesn't exist
        """
        if not self.file_path.exists():
            msg = f"File not found: {self.file_path}"
            raise FileWatcherError(msg)

        self._monitoring_thread = threading.Thread(
            target=self._monitor_loop, daemon=True, name="FileWatcher"
        )
        self._monitoring_thread.start()
        logger.info("FileWatcher monitoring started")

    def stop(self) -> None:
        """
        Stop monitoring and wait for thread to exit.

        Processes any remaining content below threshold before shutdown.
        Saves state before exit. Idempotent.
        """
        if self._monitoring_thread is None:
            return

        logger.info("FileWatcher shutdown requested")

        # Process remaining content before shutdown (flush)
        try:
            self._check_and_trigger(flush=True)
        except Exception:
            logger.exception("Error during final flush")

        self._shutdown_event.set()

        # Wait for thread to exit
        self._monitoring_thread.join(timeout=10.0)
        if self._monitoring_thread.is_alive():
            logger.warning("FileWatcher thread did not exit cleanly")

        # Save final state
        self._save_state()
        logger.info("FileWatcher stopped")

    def get_last_offset(self) -> int:
        """
        Get current byte offset in file.

        Thread-safe.

        Returns:
            Last processed byte offset
        """
        with self._offset_lock:
            return self._last_processed_offset

    def _monitor_loop(self) -> None:
        """
        Main monitoring loop (runs in background thread).

        Polls file every polling_interval seconds. Checks for new content
        and evaluates threshold. Exits when shutdown_event is set.
        """
        logger.debug("Monitoring loop started")

        while not self._shutdown_event.is_set():
            try:
                self._check_and_trigger()
            except Exception:
                logger.exception("Error in monitoring loop")
                # Continue monitoring despite errors

            # Wait for next polling cycle (or shutdown)
            self._shutdown_event.wait(self.polling_interval)

        logger.debug("Monitoring loop exited")

    def _check_and_trigger(self, flush: bool = False) -> None:
        """
        Check file for new content and trigger translation if threshold met.

        Args:
            flush: If True, force translation regardless of threshold

        Updates offset and saves state when translation triggered.
        """
        # Check file size
        try:
            current_size = self.file_path.stat().st_size
        except FileNotFoundError:
            logger.warning("File disappeared: %s", self.file_path)
            return

        # Read new content if file grew
        with self._offset_lock:
            last_offset = self._last_processed_offset

        if current_size <= last_offset:
            # No new content
            return

        # Read new content
        with self.file_path.open(encoding="utf-8") as f:
            f.seek(last_offset)
            new_content = f.read(current_size - last_offset)

        if not new_content:
            return

        # Count tokens in new content
        token_count = self.token_counter.count_tokens(new_content)
        logger.debug(
            "Detected %d bytes, %d tokens at offset %d",
            len(new_content),
            token_count,
            last_offset,
        )

        # Check threshold (or force if flushing)
        should_translate = flush or token_count >= self.min_tokens
        if should_translate:
            if flush:
                logger.info(
                    "Flush requested, translating remaining %d tokens",
                    token_count,
                )
            else:
                logger.info(
                    "Threshold exceeded (%d >= %d), triggering translation",
                    token_count,
                    self.min_tokens,
                )

            # Trigger translation callback
            try:
                self.translation_callback(new_content, last_offset)
            except Exception:
                logger.exception("Translation callback failed")
                # Don't update offset if callback failed
                return

            # Update offset only after successful translation trigger
            with self._offset_lock:
                self._last_processed_offset = current_size

            # Save state
            self._save_state()
        # else: Keep offset unchanged to accumulate tokens across polling cycles

    def _load_state(self) -> None:
        """
        Load state from disk.

        If state file doesn't exist or is corrupted, starts from offset 0.
        """
        if not self.state_file.exists():
            logger.debug("No state file found, starting from offset 0")
            return

        try:
            with self.state_file.open(encoding="utf-8") as f:
                state = json.load(f)

            self._last_processed_offset = state.get("last_processed_offset", 0)
            logger.info(
                "State loaded from %s: offset=%d",
                self.state_file,
                self._last_processed_offset,
            )

        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Failed to load state file: %s. Starting from offset 0", e)
            self._last_processed_offset = 0

    def _save_state(self) -> None:
        """
        Save state to disk.

        Writes offset, timestamp, and metadata to JSON file.
        """
        with self._offset_lock:
            state = {
                "version": "1.0",
                "last_processed_offset": self._last_processed_offset,
                "last_check_timestamp": datetime.now().isoformat(),
            }

        try:
            with self.state_file.open("w", encoding="utf-8") as f:
                json.dump(state, f, indent=2)
            logger.debug("State saved to %s", self.state_file)
        except OSError:
            logger.exception("Failed to save state")
