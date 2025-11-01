# GENERATED FROM SPEC-CONCURRENT-TRANSLATION-001

import queue
import time
from unittest.mock import Mock

from src.core.streaming_translator import (
    PermanentTranslationError,
    StreamingTranslator,
    TransientTranslationError,
)
from src.core.translation_worker import TranslationResult, TranslationWorker

# Constants for magic values
INSTANT_THRESHOLD = 0.1
TEST_OFFSET = 12345


class TestTranslationWorker:
    # Trace: SPEC-CONCURRENT-TRANSLATION-001, TEST-CONCURRENT-001-AC3
    def test_async_translation(self):
        """AC-3: Translation runs without blocking caller"""
        translator = Mock(spec=StreamingTranslator)
        translator.chunk_generator.return_value = [(1, "Test content to translate")]
        translator._invoke_model.return_value = "번역된 내용"
        translator.max_token_length = 8000
        translator.max_retries = 2
        translator.retry_backoff_seconds = 0.0

        result_queue: queue.Queue[TranslationResult] = queue.Queue()
        worker = TranslationWorker(translator=translator, result_queue=result_queue)

        content = "Test content to translate"
        start = time.time()

        # translate_async should return immediately
        worker.translate_async(content, offset=0)

        elapsed = time.time() - start
        assert elapsed < INSTANT_THRESHOLD  # Should be nearly instant

        # Wait for background thread to complete
        result = result_queue.get(timeout=2.0)

        assert result.successes == 1
        assert result.failures == 0
        assert result.translated_text is not None

    # Trace: SPEC-CONCURRENT-TRANSLATION-001, TEST-CONCURRENT-001-AC4
    def test_concurrent_queueing(self):
        """AC-4: Multiple batches queued correctly"""
        translator = Mock(spec=StreamingTranslator)
        translator.max_token_length = 8000
        translator.max_retries = 2
        translator.retry_backoff_seconds = 0.0
        translator.chunk_generator.return_value = [(1, "Test")]

        # Simulate slow translation
        def slow_translate(_chunk_idx, _chunk_text):
            time.sleep(0.2)
            return "Translated"

        translator._invoke_model.side_effect = slow_translate

        result_queue: queue.Queue[TranslationResult] = queue.Queue()
        worker = TranslationWorker(translator=translator, result_queue=result_queue)

        # Queue two translations
        worker.translate_async("First batch", offset=0)
        worker.translate_async("Second batch", offset=100)

        # Both should be queued
        result1 = result_queue.get(timeout=1.0)
        result2 = result_queue.get(timeout=1.0)

        assert result1 is not None
        assert result2 is not None

    # Trace: SPEC-CONCURRENT-TRANSLATION-001, TEST-CONCURRENT-001-AC10
    def test_error_handling(self):
        """AC-10: Translation errors logged without crash"""
        translator = Mock(spec=StreamingTranslator)
        translator.max_token_length = 8000
        translator.max_retries = 2
        translator.retry_backoff_seconds = 0.0
        translator.chunk_generator.return_value = [(1, "Content")]
        translator._invoke_model.side_effect = TransientTranslationError("API error")

        result_queue: queue.Queue[TranslationResult] = queue.Queue()
        worker = TranslationWorker(translator=translator, result_queue=result_queue)

        # Should not raise exception
        worker.translate_async("Content", offset=0)

        # Wait for worker to process
        time.sleep(0.5)

        # Result should indicate failure
        result = result_queue.get(timeout=1.0)
        assert result.failures > 0 or result.error is not None

    # Trace: SPEC-CONCURRENT-TRANSLATION-001, TEST-CONCURRENT-001-AC10
    def test_permanent_error_skip_chunk(self):
        """Permanent errors skip chunk and continue"""
        translator = Mock(spec=StreamingTranslator)
        translator.max_token_length = 8000
        translator.max_retries = 2
        translator.retry_backoff_seconds = 0.0
        translator.chunk_generator.return_value = [(1, "Content")]
        translator._invoke_model.side_effect = PermanentTranslationError(
            "Empty response"
        )

        result_queue: queue.Queue[TranslationResult] = queue.Queue()
        worker = TranslationWorker(translator=translator, result_queue=result_queue)

        worker.translate_async("Content", offset=0)
        time.sleep(0.5)

        result = result_queue.get(timeout=1.0)
        assert result.failures >= 1
        assert result.successes == 0

    # Trace: SPEC-CONCURRENT-TRANSLATION-001, TEST-CONCURRENT-001-AC3
    def test_result_includes_offset(self):
        """Translation result includes original offset"""
        translator = Mock(spec=StreamingTranslator)
        translator.max_token_length = 8000
        translator.max_retries = 2
        translator.retry_backoff_seconds = 0.0
        translator.chunk_generator.return_value = [(1, "Content")]
        translator._invoke_model.return_value = "Translated"

        result_queue: queue.Queue[TranslationResult] = queue.Queue()
        worker = TranslationWorker(translator=translator, result_queue=result_queue)

        worker.translate_async("Content", offset=TEST_OFFSET)

        result = result_queue.get(timeout=1.0)
        assert result.start_offset == TEST_OFFSET

    # Trace: SPEC-CONCURRENT-TRANSLATION-001, TEST-CONCURRENT-001-AC6
    def test_thread_safety_queue_operations(self):
        """Queue operations are thread-safe"""
        translator = Mock(spec=StreamingTranslator)
        translator.max_token_length = 8000
        translator.max_retries = 2
        translator.retry_backoff_seconds = 0.0
        translator.chunk_generator.return_value = [(1, "Content")]
        translator._invoke_model.return_value = "Translated"

        result_queue: queue.Queue[TranslationResult] = queue.Queue()
        worker = TranslationWorker(translator=translator, result_queue=result_queue)

        # Start multiple translations concurrently
        num_translations = 10
        for i in range(num_translations):
            worker.translate_async(f"Content {i}", offset=i * 100)

        # Collect all results
        results = []
        for _ in range(num_translations):
            result = result_queue.get(timeout=2.0)
            results.append(result)

        # Verify all results received
        assert len(results) == num_translations
        offsets = [r.start_offset for r in results]
        assert len(set(offsets)) == num_translations  # All unique
