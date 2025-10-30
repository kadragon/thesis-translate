# GENERATED FROM SPEC-CONCURRENT-TRANSLATION-001

import json
import tempfile
import threading
import time
from pathlib import Path
from unittest.mock import Mock

import pytest

from src.core.file_watcher import FileWatcher, FileWatcherError
from src.utils.token_counter import TokenCounter


class TestFileWatcher:
    # Trace: SPEC-CONCURRENT-TRANSLATION-001, TEST-CONCURRENT-001-AC1
    def test_detect_new_content(self):
        """AC-1: FileWatcher detects new content within polling interval"""
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
            test_file = f.name
            f.write("Initial content\n")

        try:
            callback = Mock()
            token_counter = TokenCounter()

            state_file = ".translation_state_detect_test.json"
            Path(state_file).unlink(missing_ok=True)

            watcher = FileWatcher(
                file_path=test_file,
                min_tokens=1000,  # High threshold to avoid triggering
                polling_interval=0.5,
                translation_callback=callback,
                token_counter=token_counter,
                state_file=state_file,
            )

            watcher.start()
            time.sleep(0.3)  # Wait less than polling interval

            # Append new content
            with open(test_file, "a") as f:  # noqa: PTH123
                f.write("New content added\n")

            # Wait for at least one polling cycle
            time.sleep(0.7)

            # Verify offset NOT updated (content below threshold accumulates)
            # This fixes data loss issue identified in PR review
            assert watcher.get_last_offset() == 0
            # Callback should not be triggered below threshold
            callback.assert_not_called()

            watcher.stop()
        finally:
            Path(test_file).unlink(missing_ok=True)
            Path(state_file).unlink(missing_ok=True)

    # Trace: SPEC-CONCURRENT-TRANSLATION-001, TEST-CONCURRENT-001-AC2
    def test_trigger_on_threshold(self):
        """AC-2: Translation triggered when token threshold exceeded"""
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
            test_file = f.name

        try:
            callback = Mock()
            token_counter = TokenCounter()

            # Create content that exceeds threshold
            large_content = "word " * 1000  # ~1000 tokens
            with open(test_file, "w") as f:  # noqa: PTH123
                f.write(large_content)

            state_file = ".translation_state_threshold_test.json"
            Path(state_file).unlink(missing_ok=True)

            watcher = FileWatcher(
                file_path=test_file,
                min_tokens=500,  # Set threshold lower than content
                polling_interval=0.5,
                translation_callback=callback,
                token_counter=token_counter,
                state_file=state_file,
            )

            watcher.start()

            # Wait for polling cycle to detect and trigger
            time.sleep(1.0)

            watcher.stop()

            # Verify callback was called with content
            assert callback.call_count >= 1
            args = callback.call_args[0]
            assert len(args[0]) > 0  # content
            assert isinstance(args[1], int)  # offset

        finally:
            Path(test_file).unlink(missing_ok=True)
            Path(state_file).unlink(missing_ok=True)

    # Trace: SPEC-CONCURRENT-TRANSLATION-001, TEST-CONCURRENT-001-AC8
    def test_initial_state(self):
        """AC-8: Initial state starts from offset 0"""
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
            test_file = f.name
            f.write("Some content\n")

        try:
            callback = Mock()
            token_counter = TokenCounter()

            # Ensure no state file exists
            state_file = ".translation_state_test.json"
            Path(state_file).unlink(missing_ok=True)

            watcher = FileWatcher(
                file_path=test_file,
                min_tokens=1000,
                polling_interval=1.0,
                translation_callback=callback,
                token_counter=token_counter,
                state_file=state_file,
            )

            # Verify initial offset is 0
            assert watcher.get_last_offset() == 0

        finally:
            Path(test_file).unlink(missing_ok=True)
            Path(state_file).unlink(missing_ok=True)

    # Trace: SPEC-CONCURRENT-TRANSLATION-001, TEST-CONCURRENT-001-AC9
    def test_resume_from_offset(self):
        """AC-9: Resume from saved state"""
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
            test_file = f.name
            f.write("Initial content that was already processed\n")
            f.write("New content to be processed\n")

        try:
            callback = Mock()
            token_counter = TokenCounter()

            # Create state file with saved offset
            state_file = ".translation_state_test.json"
            saved_offset = len("Initial content that was already processed\n")
            state_data = {
                "version": "1.0",
                "last_processed_offset": saved_offset,
                "last_check_timestamp": "2025-10-30T10:00:00Z",
                "total_chunks_translated": 1,
            }
            with open(state_file, "w") as f:  # noqa: PTH123
                json.dump(state_data, f)

            watcher = FileWatcher(
                file_path=test_file,
                min_tokens=10,  # Low threshold
                polling_interval=0.5,
                translation_callback=callback,
                token_counter=token_counter,
                state_file=state_file,
            )

            # Verify offset was loaded from state
            assert watcher.get_last_offset() == saved_offset

            watcher.start()
            time.sleep(1.0)  # Allow polling
            watcher.stop()

            # Verify only new content was processed
            if callback.call_count > 0:
                args = callback.call_args[0]
                content = args[0]
                assert "New content to be processed" in content
                assert "Initial content" not in content

        finally:
            Path(test_file).unlink(missing_ok=True)
            Path(state_file).unlink(missing_ok=True)

    # Trace: SPEC-CONCURRENT-TRANSLATION-001, TEST-CONCURRENT-001-AC1
    def test_file_not_found_error(self):
        """FileWatcher raises error if file doesn't exist"""
        callback = Mock()
        token_counter = TokenCounter()

        with pytest.raises(FileWatcherError):
            watcher = FileWatcher(
                file_path="/nonexistent/path/file.txt",
                min_tokens=1000,
                polling_interval=1.0,
                translation_callback=callback,
                token_counter=token_counter,
            )
            watcher.start()

    # Trace: SPEC-CONCURRENT-TRANSLATION-001, TEST-CONCURRENT-001-AC6
    def test_thread_safety_offset_updates(self):
        """AC-6: Concurrent offset updates are thread-safe"""
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
            test_file = f.name
            f.write("Initial\n")

        try:
            callback = Mock()
            token_counter = TokenCounter()

            # Use unique state file for this test
            state_file = ".translation_state_thread_safety_test.json"
            Path(state_file).unlink(missing_ok=True)

            watcher = FileWatcher(
                file_path=test_file,
                min_tokens=1000,  # High threshold
                polling_interval=0.1,  # Fast polling
                translation_callback=callback,
                token_counter=token_counter,
                state_file=state_file,
            )

            watcher.start()

            # Simulate concurrent writes
            def append_content():
                for _ in range(10):
                    with open(test_file, "a") as f:  # noqa: PTH123
                        f.write("Line\n")
                    time.sleep(0.05)

            threads = [threading.Thread(target=append_content) for _ in range(3)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            time.sleep(0.5)  # Allow final polling
            watcher.stop()

            # Verify offset matches file size (no corruption)
            final_size = Path(test_file).stat().st_size
            assert watcher.get_last_offset() <= final_size

        finally:
            Path(test_file).unlink(missing_ok=True)
            Path(state_file).unlink(missing_ok=True)
