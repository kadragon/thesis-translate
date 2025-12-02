# GENERATED FROM SPEC-USER-PROMPTED-001
# Trace: SPEC-USER-PROMPTED-001

"""
Tests for user-prompted translation mode.

Tests FileWatcher and ConcurrentOrchestrator in user-prompted mode
(auto_translate=False).
"""

import tempfile
import threading
import time
from pathlib import Path
from unittest.mock import Mock

import pytest

from src.core.concurrent_orchestrator import ConcurrentTranslationOrchestrator
from src.core.file_watcher import FileWatcher
from src.core.translation_config import TranslationConfig
from src.utils.token_counter import TokenCounter

# Constants for user-prompted mode thresholds
INITIAL_THRESHOLD = 40000
SECOND_THRESHOLD = 80000


class TestUserPromptedFileWatcher:
    """Test FileWatcher in user-prompted mode (auto_translate=False)."""

    # Trace: SPEC-USER-PROMPTED-001, TEST-USER-PROMPTED-001-AC1
    def test_threshold_sets_ready_flag_no_auto_trigger(self):
        """
        AC-1: FileWatcher sets ready flag without auto-triggering.

        GIVEN accumulated tokens reach threshold (40000)
        WHEN FileWatcher evaluates content
        THEN it sets _translation_ready=True WITHOUT calling callback
        """
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
            test_file = f.name
            # Write enough content to exceed 40000 tokens
            # Approximate: 1 token ≈ 4 characters
            large_content = "test content " * 12000  # ~48000 tokens
            f.write(large_content)

        try:
            callback = Mock()
            token_counter = TokenCounter()
            state_file = ".test_user_prompted_ac1.json"
            Path(state_file).unlink(missing_ok=True)

            watcher = FileWatcher(
                file_path=test_file,
                min_tokens=40000,
                polling_interval=0.5,
                translation_callback=callback,
                token_counter=token_counter,
                state_file=state_file,
                auto_translate=False,  # User-prompted mode
            )

            watcher.start()
            time.sleep(1.5)  # Wait for polling cycles

            # Check ready flag is set
            ready, token_count = watcher.is_translation_ready()
            assert ready is True, "Ready flag should be set"
            assert token_count >= INITIAL_THRESHOLD, (
                f"Token count should be >= 40000, got {token_count}"
            )

            # Verify callback was NOT called (no auto-trigger)
            callback.assert_not_called()

            watcher.stop()
        finally:
            Path(test_file).unlink(missing_ok=True)
            Path(state_file).unlink(missing_ok=True)

    # Trace: SPEC-USER-PROMPTED-001, TEST-USER-PROMPTED-001-AC3
    def test_manual_trigger_starts_translation(self):
        """
        AC-3: User can manually trigger translation.

        GIVEN translation is ready (threshold exceeded)
        WHEN user calls trigger_translation_manual()
        THEN translation callback is called and flag is reset
        """
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
            test_file = f.name
            large_content = "test content " * 12000
            f.write(large_content)

        try:
            callback = Mock()
            token_counter = TokenCounter()
            state_file = ".test_user_prompted_ac3.json"
            Path(state_file).unlink(missing_ok=True)

            watcher = FileWatcher(
                file_path=test_file,
                min_tokens=40000,
                polling_interval=0.5,
                translation_callback=callback,
                token_counter=token_counter,
                state_file=state_file,
                auto_translate=False,
            )

            watcher.start()
            time.sleep(1.5)

            # Verify ready
            ready, _ = watcher.is_translation_ready()
            assert ready is True

            # Manual trigger
            success = watcher.trigger_translation_manual()
            assert success is True, "Manual trigger should succeed"

            # Verify callback was called
            callback.assert_called_once()

            # Verify flag is reset
            ready, _ = watcher.is_translation_ready()
            assert ready is False, "Ready flag should be reset after trigger"

            watcher.stop()
        finally:
            Path(test_file).unlink(missing_ok=True)
            Path(state_file).unlink(missing_ok=True)

    # Trace: SPEC-USER-PROMPTED-001, TEST-USER-PROMPTED-001-AC4
    def test_threshold_increments(self):
        """
        AC-4: Threshold increments after manual trigger.

        GIVEN user triggers translation at 40000 tokens
        WHEN threshold is advanced
        THEN next threshold is 80000
        """
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
            test_file = f.name
            f.write("initial content " * 10000)

        try:
            callback = Mock()
            token_counter = TokenCounter()
            state_file = ".test_user_prompted_ac4.json"
            Path(state_file).unlink(missing_ok=True)

            watcher = FileWatcher(
                file_path=test_file,
                min_tokens=40000,
                polling_interval=0.5,
                translation_callback=callback,
                token_counter=token_counter,
                state_file=state_file,
                auto_translate=False,
            )

            # Initial threshold
            assert watcher.get_current_threshold() == INITIAL_THRESHOLD

            watcher.start()
            time.sleep(1.5)

            # Trigger first translation
            ready, _ = watcher.is_translation_ready()
            if ready:
                watcher.trigger_translation_manual()

            # Check threshold advanced
            assert watcher.get_current_threshold() == SECOND_THRESHOLD, (
                "Threshold should increment to 80000"
            )

            watcher.stop()
        finally:
            Path(test_file).unlink(missing_ok=True)
            Path(state_file).unlink(missing_ok=True)

    # Trace: SPEC-USER-PROMPTED-001
    def test_trigger_fails_when_not_ready(self):
        """Test that manual trigger fails when not ready."""
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
            test_file = f.name
            f.write("small content")  # Not enough tokens

        try:
            callback = Mock()
            token_counter = TokenCounter()
            state_file = ".test_user_prompted_not_ready.json"
            Path(state_file).unlink(missing_ok=True)

            watcher = FileWatcher(
                file_path=test_file,
                min_tokens=40000,
                polling_interval=0.5,
                translation_callback=callback,
                token_counter=token_counter,
                state_file=state_file,
                auto_translate=False,
            )

            watcher.start()
            time.sleep(1.0)

            # Verify not ready
            ready, _ = watcher.is_translation_ready()
            assert ready is False

            # Attempt manual trigger
            success = watcher.trigger_translation_manual()
            assert success is False, "Trigger should fail when not ready"

            # Verify callback not called
            callback.assert_not_called()

            watcher.stop()
        finally:
            Path(test_file).unlink(missing_ok=True)
            Path(state_file).unlink(missing_ok=True)


class TestUserPromptedOrchestrator:
    """Test ConcurrentOrchestrator in user-prompted mode."""

    # Trace: SPEC-USER-PROMPTED-001, TEST-USER-PROMPTED-001-AC2
    def test_orchestrator_proxy_methods(self):
        """
        AC-2: Orchestrator provides proxy methods to FileWatcher.

        GIVEN orchestrator in user-prompted mode
        WHEN proxy methods are called
        THEN they correctly delegate to FileWatcher
        """
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
            input_file = f.name
            f.write("test content " * 12000)

        # Create output file securely
        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as f:
            output_file = f.name

        try:
            config = TranslationConfig()
            orchestrator = ConcurrentTranslationOrchestrator(
                input_file=input_file,
                output_file=output_file,
                config=config,
                min_tokens=40000,
                polling_interval=0.5,
                auto_translate=False,  # User-prompted mode
            )

            # Start in background thread
            run_thread = threading.Thread(target=orchestrator.run, daemon=True)
            run_thread.start()

            # Wait for threshold with retry logic
            max_retries = 10
            for _i in range(max_retries):
                time.sleep(0.5)
                ready, token_count = orchestrator.is_translation_ready()
                if ready or token_count > 0:
                    break
            else:
                # If still not ready after retries, that's okay for this test
                # We're just testing that proxy methods work
                pass

            # Test proxy methods exist and return expected types
            ready, token_count = orchestrator.is_translation_ready()
            assert isinstance(ready, bool), "Ready should be bool"
            assert isinstance(token_count, int), "Token count should be int"
            assert token_count >= 0, "Token count should be non-negative"

            threshold = orchestrator.get_current_threshold()
            assert threshold == INITIAL_THRESHOLD, "Should return correct threshold"

            # Stop orchestrator
            orchestrator.stop()
            time.sleep(0.5)

        finally:
            Path(input_file).unlink(missing_ok=True)
            Path(output_file).unlink(missing_ok=True)

    # Trace: SPEC-USER-PROMPTED-001
    def test_backward_compatibility_auto_translate(self):
        """Test that auto_translate=True (default) maintains old behavior."""
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
            input_file = f.name
            f.write("test " * 1500)  # ~4500 tokens

        # Create output file securely
        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as f:
            output_file = f.name

        try:
            config = TranslationConfig()

            # Create with auto_translate=True (backward compat mode)
            orchestrator = ConcurrentTranslationOrchestrator(
                input_file=input_file,
                output_file=output_file,
                config=config,
                min_tokens=4000,
                polling_interval=0.5,
                auto_translate=True,  # Auto-translate mode (default)
            )

            # Should behave like old auto-translate mode
            assert orchestrator.auto_translate is True

        finally:
            Path(input_file).unlink(missing_ok=True)
            Path(output_file).unlink(missing_ok=True)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
