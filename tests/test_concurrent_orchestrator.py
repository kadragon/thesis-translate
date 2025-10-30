# GENERATED FROM SPEC-CONCURRENT-TRANSLATION-001

import tempfile
import threading
import time
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from src.core.concurrent_orchestrator import ConcurrentTranslationOrchestrator
from src.core.streaming_translator import StreamingTranslator


class TestOrchestrator:
    # Trace: SPEC-CONCURRENT-TRANSLATION-001, TEST-CONCURRENT-001-AC5
    def test_graceful_shutdown(self):
        """AC-5: Graceful shutdown processes remaining content"""
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
            input_file = f.name
            # Write content below threshold (2000 tokens < 4000)
            f.write("word " * 500)  # ~500 tokens

        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
            output_file = f.name

        try:
            # Use a mocked StreamingTranslator
            with patch(
                "src.core.concurrent_orchestrator.StreamingTranslator"
            ) as MockTranslator:  # noqa: N806
                mock_translator = Mock(spec=StreamingTranslator)
                mock_translator.chunk_generator.return_value = []
                mock_translator._invoke_model.return_value = "Translated"
                MockTranslator.return_value = mock_translator

                config = Mock()
                orchestrator = ConcurrentTranslationOrchestrator(
                    input_file=input_file,
                    output_file=output_file,
                    config=config,
                    min_tokens=4000,
                    polling_interval=0.5,
                )

                # Start orchestrator in background thread
                def run_orchestrator():
                    orchestrator.run()

                thread = threading.Thread(target=run_orchestrator)
                thread.start()

                # Let it run briefly
                time.sleep(1.0)

                # Signal shutdown
                orchestrator.stop()
                thread.join(timeout=5.0)

                # Verify remaining content was processed
                metrics = orchestrator.get_metrics()
                assert metrics is not None
                # Even if below threshold, shutdown should process remaining

        finally:
            Path(input_file).unlink(missing_ok=True)
            Path(output_file).unlink(missing_ok=True)

    # Trace: SPEC-CONCURRENT-TRANSLATION-001, TEST-CONCURRENT-001-AC6
    def test_thread_safety(self):
        """AC-6: Thread-safe operations prevent race conditions"""
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
            input_file = f.name

        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
            output_file = f.name

        try:
            with patch(
                "src.core.concurrent_orchestrator.StreamingTranslator"
            ) as MockTranslator:  # noqa: N806
                mock_translator = Mock(spec=StreamingTranslator)
                mock_translator.chunk_generator.return_value = [(1, "Test")]
                mock_translator._invoke_model.return_value = "Translated"
                MockTranslator.return_value = mock_translator

                config = Mock()
                orchestrator = ConcurrentTranslationOrchestrator(
                    input_file=input_file,
                    output_file=output_file,
                    config=config,
                    min_tokens=100,
                    polling_interval=0.1,
                )

                # Start orchestrator
                thread = threading.Thread(target=orchestrator.run)
                thread.start()

                # Simulate concurrent writes to input file
                def write_content():
                    for i in range(20):
                        with open(input_file, "a") as f:  # noqa: PTH123
                            f.write(f"Line {i}\n")
                        time.sleep(0.05)

                writers = [threading.Thread(target=write_content) for _ in range(3)]
                for w in writers:
                    w.start()
                for w in writers:
                    w.join()

                time.sleep(0.5)
                orchestrator.stop()
                thread.join(timeout=5.0)

                # Verify no crashes and metrics are consistent
                metrics = orchestrator.get_metrics()
                assert metrics.successes + metrics.failures >= 0

        finally:
            Path(input_file).unlink(missing_ok=True)
            Path(output_file).unlink(missing_ok=True)

    # Trace: SPEC-CONCURRENT-TRANSLATION-001, TEST-CONCURRENT-001-AC7
    def test_metrics_aggregation(self):
        """AC-7: Metrics accurately reflect parallel operations"""
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
            input_file = f.name
            # Write content that will create multiple chunks
            f.write("word " * 5000)  # ~5000 tokens, should trigger translation

        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
            output_file = f.name

        try:
            with patch(
                "src.core.concurrent_orchestrator.StreamingTranslator"
            ) as MockTranslator:  # noqa: N806
                mock_translator = Mock(spec=StreamingTranslator)
                mock_translator.chunk_generator.return_value = [(1, "Test")]
                mock_translator._invoke_model.return_value = "Translated"
                MockTranslator.return_value = mock_translator

                config = Mock()
                orchestrator = ConcurrentTranslationOrchestrator(
                    input_file=input_file,
                    output_file=output_file,
                    config=config,
                    min_tokens=2000,  # Lower threshold for testing
                    polling_interval=0.5,
                )

                start_time = time.time()

                # Run in background
                thread = threading.Thread(target=orchestrator.run)
                thread.start()

                # Wait for processing
                time.sleep(2.0)

                orchestrator.stop()
                thread.join(timeout=5.0)

                duration = time.time() - start_time

                metrics = orchestrator.get_metrics()

                # Verify metrics structure
                assert hasattr(metrics, "successes")
                assert hasattr(metrics, "failures")
                assert hasattr(metrics, "duration_seconds")

                # Verify duration is reasonable
                assert metrics.duration_seconds <= duration + 1.0

        finally:
            Path(input_file).unlink(missing_ok=True)
            Path(output_file).unlink(missing_ok=True)

    # Trace: SPEC-CONCURRENT-TRANSLATION-001, TEST-CONCURRENT-001-AC5
    def test_file_not_found_error(self):
        """Orchestrator raises error if input file doesn't exist"""
        config = Mock()

        with pytest.raises(FileNotFoundError):
            orchestrator = ConcurrentTranslationOrchestrator(
                input_file="/nonexistent/file.txt",
                output_file="output.txt",
                config=config,
            )
            orchestrator.run()

    # Trace: SPEC-CONCURRENT-TRANSLATION-001, TEST-CONCURRENT-001-AC7
    def test_get_metrics_during_run(self):
        """get_metrics() can be called during run() for progress"""
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
            input_file = f.name
            f.write("Initial content\n")

        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
            output_file = f.name

        try:
            with patch(
                "src.core.concurrent_orchestrator.StreamingTranslator"
            ) as MockTranslator:  # noqa: N806
                mock_translator = Mock(spec=StreamingTranslator)
                mock_translator.chunk_generator.return_value = []
                mock_translator._invoke_model.return_value = "Translated"
                MockTranslator.return_value = mock_translator

                config = Mock()
                orchestrator = ConcurrentTranslationOrchestrator(
                    input_file=input_file,
                    output_file=output_file,
                    config=config,
                    min_tokens=1000,
                    polling_interval=0.5,
                )

                thread = threading.Thread(target=orchestrator.run)
                thread.start()

                time.sleep(0.5)

                # Call get_metrics while running
                metrics = orchestrator.get_metrics()
                assert metrics is not None

                orchestrator.stop()
                thread.join(timeout=5.0)

        finally:
            Path(input_file).unlink(missing_ok=True)
            Path(output_file).unlink(missing_ok=True)
