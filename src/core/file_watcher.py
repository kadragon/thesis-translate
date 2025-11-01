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
        auto_translate: bool = True,
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
            auto_translate: If True, auto-trigger translation; If False,
                notify only (user-prompted mode)

        Raises:
            FileWatcherError: If file_path doesn't exist or invalid params
        """
        self.file_path = Path(file_path)
        self.min_tokens = min_tokens
        self.polling_interval = max(polling_interval, 0.5)
        self.translation_callback = translation_callback
        self.token_counter = token_counter
        self.state_file = Path(state_file)
        self.auto_translate = auto_translate

        # Thread coordination
        self._monitoring_thread: threading.Thread | None = None
        self._shutdown_event = threading.Event()
        self._offset_lock = threading.Lock()

        # State
        self._last_processed_offset = 0

        # User-prompted mode state (SPEC-USER-PROMPTED-001)
        self._translation_ready = False
        self._ready_token_count = 0
        self._next_threshold = min_tokens  # Initial threshold
        self._accumulated_content = ""  # Content ready for translation

        # Load state from disk
        self._load_state()

        logger.info(
            "FileWatcher initialized: file=%s, "
            "min_tokens=%d, interval=%.1fs, resume_offset=%d, auto_translate=%s",
            file_path,
            min_tokens,
            polling_interval,
            self._last_processed_offset,
            auto_translate,
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

    def is_translation_ready(self) -> tuple[bool, int]:
        """
        Check if translation is ready to be triggered by user.

        Returns:
            Tuple of (ready: bool, token_count: int)
            - ready: True if accumulated tokens >= current threshold
            - token_count: Number of tokens available for translation

        Thread-safe: Uses offset_lock
        """
        with self._offset_lock:
            return (self._translation_ready, self._ready_token_count)

    def trigger_translation_manual(self) -> bool:
        """
        Manually trigger translation for accumulated content.

        Called when user presses 'T' in TextPreprocessor menu.
        Resets ready flag and advances to next threshold.

        Returns:
            bool: True if translation was triggered, False if not ready

        Side effects:
            - Calls translation_callback with accumulated content
            - Updates _next_threshold
            - Resets _translation_ready flag
            - Updates _last_processed_offset
        """
        with self._offset_lock:
            if not self._translation_ready:
                logger.warning("Translation not ready")
                return False

            content = self._accumulated_content
            offset = self._last_processed_offset
            current_tokens = self._ready_token_count

        # Trigger translation callback (outside lock)
        try:
            logger.info(
                "Manual translation trigger: %d tokens at offset %d",
                current_tokens,
                offset,
            )
            self.translation_callback(content, offset)
        except Exception:
            logger.exception("Translation callback failed")
            return False

        # Update state after successful trigger
        with self._offset_lock:
            # Calculate bytes actually sent to translation
            content_bytes = len(content.encode("utf-8"))

            # Only advance offset by bytes we actually translated
            # This prevents race condition where watcher adds content between
            # releasing and re-acquiring lock
            self._last_processed_offset = offset + content_bytes

            # Remove translated content from accumulated buffer
            # Keep any new content that was added concurrently
            if self._accumulated_content.startswith(content):
                self._accumulated_content = self._accumulated_content[len(content) :]
                logger.debug(
                    "Removed %d chars from buffer, %d remaining",
                    len(content),
                    len(self._accumulated_content),
                )
            else:
                # Safety: if content doesn't match (shouldn't happen), clear it
                logger.warning(
                    "Accumulated content mismatch, clearing buffer (data loss possible)"
                )
                self._accumulated_content = ""

            # Advance threshold
            self._next_threshold += self.min_tokens
            logger.info("Next threshold: %d tokens", self._next_threshold)

            # Reset ready state
            self._translation_ready = False
            self._ready_token_count = 0

        # Save state
        self._save_state()

        return True

    def get_current_threshold(self) -> int:
        """
        Get the current threshold value.

        Returns:
            int: Current threshold (40000, 80000, 120000, etc.)
        """
        with self._offset_lock:
            return self._next_threshold

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

        # Flush mode: translate accumulated content regardless of auto_translate
        if flush and not self.auto_translate:
            self._handle_flush_mode(new_content, last_offset, current_size)
            return

        # User-prompted mode: accumulate and notify
        if not self.auto_translate:
            self._handle_user_prompted_mode(new_content)
            return

        # Auto-translate mode: original behavior
        self._handle_auto_translate_mode(new_content, last_offset, current_size, flush)

    def _handle_flush_mode(
        self, new_content: str, last_offset: int, current_size: int
    ) -> None:
        """Handle flush mode for user-prompted translation."""
        with self._offset_lock:
            self._accumulated_content += new_content
            content_to_translate = self._accumulated_content
            total_tokens = self.token_counter.count_tokens(content_to_translate)

        if content_to_translate and total_tokens > 0:
            logger.info(
                "Flush requested, translating %d accumulated tokens", total_tokens
            )
            try:
                self.translation_callback(content_to_translate, last_offset)
                with self._offset_lock:
                    self._last_processed_offset = current_size
                    self._accumulated_content = ""
                    self._translation_ready = False
                self._save_state()
            except Exception:
                logger.exception("Translation callback failed during flush")

    def _handle_user_prompted_mode(self, new_content: str) -> None:
        """Handle user-prompted mode: accumulate content and set ready flag."""
        with self._offset_lock:
            self._accumulated_content += new_content
            total_tokens = self.token_counter.count_tokens(self._accumulated_content)
            logger.debug(
                "Accumulated %d bytes, %d total tokens (threshold: %d)",
                len(new_content),
                total_tokens,
                self._next_threshold,
            )

            if total_tokens >= self._next_threshold and not self._translation_ready:
                self._translation_ready = True
                self._ready_token_count = total_tokens
                logger.info(
                    "Translation ready: %d tokens >= %d threshold",
                    total_tokens,
                    self._next_threshold,
                )

    def _handle_auto_translate_mode(
        self, new_content: str, last_offset: int, current_size: int, flush: bool
    ) -> None:
        """Handle auto-translate mode: trigger translation when threshold met."""
        token_count = self.token_counter.count_tokens(new_content)
        logger.debug(
            "Detected %d bytes, %d tokens at offset %d",
            len(new_content),
            token_count,
            last_offset,
        )

        should_translate = flush or token_count >= self.min_tokens
        if should_translate:
            if flush:
                logger.info(
                    "Flush requested, translating remaining %d tokens", token_count
                )
            else:
                logger.info(
                    "Threshold exceeded (%d >= %d), triggering translation",
                    token_count,
                    self.min_tokens,
                )

            try:
                self.translation_callback(new_content, last_offset)
            except Exception:
                logger.exception("Translation callback failed")
                return

            with self._offset_lock:
                self._last_processed_offset = current_size
            self._save_state()

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
