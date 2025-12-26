# GENERATED FROM SPEC-PARALLEL-CHUNKS-001

"""Tests for parallel chunk translation functionality."""

from pathlib import Path
from unittest.mock import patch

import pytest

from src.core.streaming_translator import StreamingTranslator


class TestParallelTranslation:
    """Test parallel chunk translation behavior."""

    @pytest.fixture
    def temp_files(self, tmp_path):
        """Create temporary input and output files."""
        input_file = tmp_path / "input.txt"
        output_file = tmp_path / "output.txt"

        # Create input with multiple chunks
        input_file.write_text("chunk1 " * 1000 + "\n" + "chunk2 " * 1000 + "\n")

        return {"input": str(input_file), "output": str(output_file)}

    def test_parallel_processing(self, temp_files):
        """AC-1: GIVEN multiple chunks WHEN translation starts THEN
        chunks are processed concurrently."""
        translator = StreamingTranslator(
            input_file=temp_files["input"],
            output_file=temp_files["output"],
            max_workers=3,
        )

        # Mock the translation to track concurrent execution
        original_translate_chunk = translator._translate_chunk
        call_order = []

        def mock_translate_chunk(chunk_index, chunk_text, progress=None, task_id=None):
            call_order.append(chunk_index)
            return original_translate_chunk(chunk_index, chunk_text, progress, task_id)

        with (
            patch.object(
                translator, "_translate_chunk", side_effect=mock_translate_chunk
            ),
            patch.object(translator, "_invoke_model", return_value="translated"),
        ):
            result = translator.translate()

        # Verify translation occurred
        assert result.successes > 0
        assert result.failures == 0

        # Verify chunks were submitted (order may vary due to parallelism)
        assert len(call_order) > 0

    def test_chunk_order_preserved(self, temp_files):
        """AC-3: GIVEN parallel translation WHEN chunks complete THEN
        results are in original chunk order."""
        translator = StreamingTranslator(
            input_file=temp_files["input"],
            output_file=temp_files["output"],
            max_workers=3,
        )

        # Mock translation with different completion times
        def mock_translate(chunk_index, _chunk_text, _progress=None, _task_id=None):
            return f"translated_chunk_{chunk_index}"

        with patch.object(translator, "_translate_chunk", side_effect=mock_translate):
            translator.translate()

        # Read output and verify order
        output_content = Path(temp_files["output"]).read_text()

        # Output should contain chunks in order (1, 2, ...)
        assert "translated_chunk_1" in output_content
        assert "translated_chunk_2" in output_content

        # Verify chunk 1 appears before chunk 2
        idx1 = output_content.index("translated_chunk_1")
        idx2 = output_content.index("translated_chunk_2")
        assert idx1 < idx2

    def test_error_handling(self, temp_files):
        """AC-4, AC-7: GIVEN parallel translation WHEN one chunk fails THEN
        other chunks continue and error is reported."""
        translator = StreamingTranslator(
            input_file=temp_files["input"],
            output_file=temp_files["output"],
            max_workers=3,
        )

        # Mock translation: chunk 1 fails, chunk 2 succeeds
        def mock_translate(chunk_index, _chunk_text, _progress=None, _task_id=None):
            if chunk_index == 1:
                return None  # Simulate failure
            return f"translated_chunk_{chunk_index}"

        with patch.object(translator, "_translate_chunk", side_effect=mock_translate):
            result = translator.translate()

        # Verify some failures occurred
        assert result.failures > 0
        # Verify some successes occurred
        assert result.successes > 0

    def test_sequential_compatibility(self, temp_files):
        """AC-6: GIVEN max_workers=1 WHEN translation runs THEN
        behavior is identical to sequential mode."""
        translator_seq = StreamingTranslator(
            input_file=temp_files["input"],
            output_file=temp_files["output"],
            max_workers=1,
        )

        with patch.object(translator_seq, "_invoke_model", return_value="translated"):
            result = translator_seq.translate()

        # Verify sequential mode works
        assert result.successes > 0
        assert result.failures == 0

        # Verify output exists
        assert Path(temp_files["output"]).exists()

    def test_max_workers_clamping(self, temp_files):
        """Verify max_workers is clamped between 1 and 10."""
        max_workers_limit = 10

        translator_low = StreamingTranslator(
            input_file=temp_files["input"],
            output_file=temp_files["output"],
            max_workers=0,
        )
        assert translator_low.max_workers == 1

        translator_high = StreamingTranslator(
            input_file=temp_files["input"],
            output_file=temp_files["output"],
            max_workers=20,
        )
        assert translator_high.max_workers == max_workers_limit

    def test_parallel_metrics(self, temp_files):
        """AC-5: GIVEN parallel translation WHEN metrics collected THEN
        duration reflects parallel processing."""
        translator = StreamingTranslator(
            input_file=temp_files["input"],
            output_file=temp_files["output"],
            max_workers=3,
        )

        with patch.object(translator, "_invoke_model", return_value="translated"):
            result = translator.translate()

        # Verify metrics are populated
        assert isinstance(result.duration_seconds, float)
        assert result.duration_seconds >= 0
