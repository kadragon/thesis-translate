# GENERATED FROM SPEC-TRANSLATION-001

from unittest.mock import Mock, patch

import pytest
from rich.progress import Progress, TaskID

from src.core.streaming_translator import (
    NoOpProgress,
    StreamingTranslator,
    TranslationError,
    TranslationRunResult,
)


def _build_config(prompt: str = "Translate: {text}") -> Mock:
    config = Mock()
    config.PROMPT_TEMPLATE = prompt
    config.glossary = "glossary"
    config.model = "gpt-4"
    config.temperature = 0.5
    return config


def _create_streaming_response(content: str | None) -> list:
    """Create a mock streaming response for OpenAI API."""
    if content is None:
        return []
    # Split content into chunks to simulate streaming
    return [Mock(choices=[Mock(delta=Mock(content=content))])]


class TestTranslator:
    # Trace: SPEC-TRANSLATION-001, TEST-TRANSLATION-001-AC2
    # Updated for SPEC-BALANCED-CHUNKS-001: balanced distribution changes
    def test_chunk_generator_deterministic(self):
        """AC-2: deterministic order with balanced distribution"""
        config = _build_config()
        with (
            patch(
                "src.core.streaming_translator.TranslationConfig", return_value=config
            ),
            patch("src.core.streaming_translator.OpenAI"),
        ):
            translator = StreamingTranslator(input_file="dummy", max_token_length=10)

        lines = ["first\n", "second\n", "third\n"]

        with patch.object(
            translator.token_counter,
            "count_tokens",
            side_effect=lambda text: len(text.splitlines()) * 5,
        ):
            chunks = list(translator.chunk_generator(lines))

        # Balanced chunking: 15 tokens total, max 10 → 2 chunks with target ~7.5 each
        # Chunk 1: first (5 tokens)
        # Chunk 2: second + third (10 tokens)
        assert chunks == [
            (1, "first\n"),
            (2, "second\nthird\n"),
        ]

    # Trace: SPEC-TRANSLATION-001, TEST-TRANSLATION-001-AC3
    @patch.object(StreamingTranslator, "_invoke_model", return_value="번역된 텍스트")
    def test_translate_chunk_success(self, mock_invoke):
        """AC-3: translating a chunk invokes the OpenAI prompt"""
        config = _build_config()
        with (
            patch(
                "src.core.streaming_translator.TranslationConfig", return_value=config
            ),
            patch("src.core.streaming_translator.OpenAI"),
        ):
            translator = StreamingTranslator(input_file="dummy")

        result = translator._translate_chunk(1, "Hello world")

        assert result == "번역된 텍스트"
        mock_invoke.assert_called_once_with(1, "Hello world", None, None)

    # Trace: SPEC-TRANSLATION-001, TEST-TRANSLATION-001-AC4
    # Trace: SPEC-TRANSLATION-001, TEST-TRANSLATION-001-AC5
    def test_translate_chunk_retry_transient(self):
        """AC-4 & AC-5: transient failures retry until success"""
        config = _build_config()
        with (
            patch(
                "src.core.streaming_translator.TranslationConfig", return_value=config
            ),
            patch("src.core.streaming_translator.OpenAI"),
        ):
            translator = StreamingTranslator(
                input_file="dummy", max_token_length=50, max_retries=2
            )

        translator.retry_backoff_seconds = 0.0
        responses = [
            TranslationError(is_transient=True, message="temporary"),
            "성공!",
        ]
        expected_calls = len(responses)

        def fake_invoke(
            _chunk_index: int, _chunk_text: str, _progress=None, _task_id=None
        ):
            result = responses.pop(0)
            if isinstance(result, Exception):
                raise result
            return result

        with patch.object(
            translator, "_invoke_model", side_effect=fake_invoke
        ) as mock_invoke:
            result = translator._translate_chunk(1, "chunk")

        assert result == "성공!"
        assert mock_invoke.call_count == expected_calls

    # Trace: SPEC-TRANSLATION-001, TEST-TRANSLATION-001-AC6
    def test_translate_chunk_retry_exhausted(self, caplog):
        """AC-6: exhausting retries skips the chunk"""
        config = _build_config()
        with (
            patch(
                "src.core.streaming_translator.TranslationConfig", return_value=config
            ),
            patch("src.core.streaming_translator.OpenAI"),
        ):
            translator = StreamingTranslator(input_file="dummy", max_retries=1)

        translator.retry_backoff_seconds = 0.0

        with (
            patch.object(
                translator,
                "_invoke_model",
                side_effect=TranslationError(
                    is_transient=True, message="still failing"
                ),
            ) as mock_invoke,
            caplog.at_level("INFO"),
        ):
            result = translator._translate_chunk(2, "data")

        assert result is None
        expected_calls = translator.max_retries + 1
        assert mock_invoke.call_count == expected_calls  # initial + retry
        assert any("chunk=2" in message for message in caplog.messages)

    # Trace: SPEC-TRANSLATION-001, TEST-TRANSLATION-001-AC7
    @patch("src.core.streaming_translator.OpenAI")
    def test_translate_success(self, mock_openai_class, tmp_path):
        """AC-1 & AC-7: translating writes chunk output to file"""
        input_file = tmp_path / "input.txt"
        output_file = tmp_path / "output.txt"
        input_file.write_text("first chunk\nsecond chunk\n")

        config = _build_config()
        mock_client = Mock()
        mock_openai_class.return_value = mock_client
        mock_client.chat.completions.create.return_value = _create_streaming_response(
            "번역 결과"
        )

        with patch(
            "src.core.streaming_translator.TranslationConfig", return_value=config
        ):
            translator = StreamingTranslator(
                input_file=str(input_file),
                output_file=str(output_file),
                max_token_length=100,
            )

        with patch.object(
            translator.token_counter,
            "count_tokens",
            side_effect=lambda text: len(text.splitlines()) * 5,
        ):
            metrics = translator.translate()

        assert output_file.read_text().strip() == "번역 결과"
        assert isinstance(metrics, TranslationRunResult)
        assert metrics.successes == 1
        assert metrics.failures == 0
        assert metrics.duration_seconds >= 0.0

    # Trace: SPEC-TRANSLATION-001, TEST-TRANSLATION-001-AC8
    def test_format_output(self, tmp_path):
        """AC-8: GIVEN output file WHEN formatting THEN lines indented consistently"""
        output_file = tmp_path / "output.txt"
        output_file.write_text("Line 1\n\nLine 2\n  Already indented\n")

        config = _build_config()
        with (
            patch(
                "src.core.streaming_translator.TranslationConfig", return_value=config
            ),
            patch("src.core.streaming_translator.OpenAI"),
        ):
            translator = StreamingTranslator(
                input_file="dummy", output_file=str(output_file)
            )

        translator.format_output()

        content = output_file.read_text()
        lines = content.split("\n")
        assert lines[0] == "  Line 1"
        assert lines[1] == ""
        assert lines[2] == "  Line 2"
        assert lines[3] == "  Already indented"

    # Trace: SPEC-TRANSLATION-001, TEST-TRANSLATION-001-AC9
    def test_translate_file_not_found(self):
        """AC-9: missing input raises FileNotFoundError"""
        config = _build_config()
        with (
            patch(
                "src.core.streaming_translator.TranslationConfig", return_value=config
            ),
            patch("src.core.streaming_translator.OpenAI"),
        ):
            translator = StreamingTranslator(input_file="nonexistent.txt")

        with pytest.raises(FileNotFoundError):
            translator.translate()

    # Trace: SPEC-TRANSLATION-001, TEST-TRANSLATION-001-AC10
    def test_translate_metrics_logging(self, tmp_path, caplog):
        """AC-10: metrics report successes and failures"""
        input_file = tmp_path / "input.txt"
        output_file = tmp_path / "output.txt"
        input_file.write_text("first\nsecond\n")

        config = _build_config()
        with (
            patch(
                "src.core.streaming_translator.TranslationConfig", return_value=config
            ),
            patch("src.core.streaming_translator.OpenAI"),
        ):
            translator = StreamingTranslator(
                input_file=str(input_file),
                output_file=str(output_file),
                max_token_length=5,
                max_retries=1,
            )

        invoke_results = [
            "성공 번역",
            TranslationError(is_transient=False, message="fatal"),
        ]

        def fake_invoke(
            _chunk_index: int, _chunk_text: str, _progress=None, _task_id=None
        ):
            result = invoke_results.pop(0)
            if isinstance(result, Exception):
                raise result
            return result

        with (
            patch.object(
                translator.token_counter,
                "count_tokens",
                side_effect=lambda text: len(text.splitlines()) * 5,
            ),
            patch.object(translator, "_invoke_model", side_effect=fake_invoke),
            caplog.at_level("INFO"),
        ):
            metrics = translator.translate()

        assert metrics.successes == 1
        assert metrics.failures == 1
        assert metrics.duration_seconds >= 0.0
        assert any(
            "successes=1" in record.message and "failures=1" in record.message
            for record in caplog.records
        )

    def test_chunk_generator_single_line_exceeds_limit(self, caplog):
        """Test that single line exceeding token limit is yielded as-is with warning"""
        config = _build_config()
        with (
            patch(
                "src.core.streaming_translator.TranslationConfig", return_value=config
            ),
            patch("src.core.streaming_translator.OpenAI"),
        ):
            translator = StreamingTranslator(input_file="dummy", max_token_length=10)

        lines = ["very long single line that exceeds the limit\n"]

        with (
            patch.object(
                translator.token_counter,
                "count_tokens",
                return_value=100,  # Exceeds max_token_length of 10
            ),
            caplog.at_level("WARNING"),
        ):
            chunks = list(translator.chunk_generator(lines))

        assert len(chunks) == 1
        assert chunks[0] == (1, "very long single line that exceeds the limit\n")
        assert any("single line over limit" in message for message in caplog.messages)

    def test_invoke_model_empty_response(self):
        """Test empty API response raises TranslationError (is_transient=False)"""
        config = _build_config()
        mock_client = Mock()
        mock_client.chat.completions.create.return_value = _create_streaming_response(
            None
        )

        with (
            patch(
                "src.core.streaming_translator.TranslationConfig", return_value=config
            ),
            patch("src.core.streaming_translator.OpenAI", return_value=mock_client),
        ):
            translator = StreamingTranslator(input_file="dummy")

        with pytest.raises(TranslationError) as exc_info:
            translator._invoke_model(1, "test chunk")
        assert exc_info.value.is_transient is False

    def test_translate_chunk_retry_with_backoff(self):
        """Test that retry logic includes sleep backoff when configured"""
        config = _build_config()
        with (
            patch(
                "src.core.streaming_translator.TranslationConfig", return_value=config
            ),
            patch("src.core.streaming_translator.OpenAI"),
        ):
            translator = StreamingTranslator(
                input_file="dummy", max_retries=2, retry_backoff_seconds=0.5
            )

        responses = [
            TranslationError(is_transient=True, message="first fail"),
            "success",
        ]

        def fake_invoke(
            _chunk_index: int, _chunk_text: str, _progress=None, _task_id=None
        ):
            result = responses.pop(0)
            if isinstance(result, Exception):
                raise result
            return result

        with (
            patch.object(translator, "_invoke_model", side_effect=fake_invoke),
            patch("src.core.streaming_translator.time.sleep") as mock_sleep,
        ):
            result = translator._translate_chunk(1, "test")

        assert result == "success"
        mock_sleep.assert_called_once_with(0.5)

    def test_translate_parallel_exception_handling(self, tmp_path, caplog):
        """Test that parallel mode handles exceptions raised by futures"""
        input_file = tmp_path / "input.txt"
        output_file = tmp_path / "output.txt"
        # Create two separate lines that will become two chunks
        input_file.write_text("line1\nline2\n")

        config = _build_config()
        with (
            patch(
                "src.core.streaming_translator.TranslationConfig", return_value=config
            ),
            patch("src.core.streaming_translator.OpenAI"),
        ):
            translator = StreamingTranslator(
                input_file=str(input_file),
                output_file=str(output_file),
                max_token_length=5,  # Small enough to create 2 chunks
                max_workers=2,
            )

        def fake_translate(
            chunk_index: int, _chunk_text: str, _progress=None, _task_id=None
        ):
            if chunk_index == 1:
                error_message = "Unexpected error"
                raise RuntimeError(error_message)
            return "success"

        with (
            patch.object(
                translator.token_counter,
                "count_tokens",
                side_effect=lambda text: len(text.splitlines()) * 5,
            ),
            patch.object(translator, "_translate_chunk", side_effect=fake_translate),
            caplog.at_level("ERROR"),
        ):
            metrics = translator.translate()

        assert metrics.failures == 1
        assert metrics.successes == 1
        assert any("raised exception" in message for message in caplog.messages)

    def test_translate_sequential_failure_counter(self, tmp_path):
        """Test that sequential mode increments failure counter correctly"""
        input_file = tmp_path / "input.txt"
        output_file = tmp_path / "output.txt"
        # Write text that will create exactly 2 chunks
        input_file.write_text("line1\nline2\n")

        config = _build_config()
        with (
            patch(
                "src.core.streaming_translator.TranslationConfig", return_value=config
            ),
            patch("src.core.streaming_translator.OpenAI"),
        ):
            translator = StreamingTranslator(
                input_file=str(input_file),
                output_file=str(output_file),
                max_token_length=5,
                max_workers=1,  # Sequential mode
            )

        failed_chunk_index = 2

        def fake_translate(
            chunk_index: int, _chunk_text: str, _progress=None, _task_id=None
        ):
            # Fail on chunk 2, succeed on chunk 1
            if chunk_index == failed_chunk_index:
                return None
            return f"success{chunk_index}"

        with (
            patch.object(
                translator.token_counter,
                "count_tokens",
                side_effect=lambda text: len(text.splitlines()) * 5,
            ),
            patch.object(translator, "_translate_chunk", side_effect=fake_translate),
        ):
            metrics = translator.translate()

        assert metrics.successes == 1
        assert metrics.failures == 1


class TestBalancedChunkDistribution:
    """Tests for SPEC-BALANCED-CHUNKS-001"""

    # Trace: SPEC-BALANCED-CHUNKS-001, AC-1, AC-2, AC-3, AC-4, AC-5
    def test_balanced_chunk_distribution(self):
        """AC-1 to AC-5: Chunks distributed evenly for parallel efficiency"""
        config = _build_config()
        with (
            patch(
                "src.core.streaming_translator.TranslationConfig", return_value=config
            ),
            patch("src.core.streaming_translator.OpenAI"),
        ):
            translator = StreamingTranslator(input_file="dummy", max_token_length=20000)

        # Simulate 27,707 tokens (similar to user's example)
        lines = [f"line{i}\n" for i in range(14)]
        token_counts = [2000] * 13 + [1707]  # Total = 27,707
        total_tokens = sum(token_counts)

        def count_tokens_mock(text: str) -> int:
            # Mock only handles single-line lookups as used by generator
            try:
                return token_counts[lines.index(text)]
            except ValueError:
                return 0

        with patch.object(
            translator.token_counter, "count_tokens", side_effect=count_tokens_mock
        ):
            chunks = list(translator.chunk_generator(lines))

        # Should create 2 chunks with balanced distribution
        expected_chunks = 2
        assert len(chunks) == expected_chunks

        # Extract chunk texts (indices unused)
        _, chunk_1_text = chunks[0]
        _, chunk_2_text = chunks[1]

        # Count tokens in each chunk
        chunk_1_lines = chunk_1_text.strip().split("\n")
        chunk_2_lines = chunk_2_text.strip().split("\n")

        chunk_1_tokens = sum(token_counts[i] for i in range(len(chunk_1_lines)))
        chunk_2_tokens = sum(
            token_counts[len(chunk_1_lines) + i] for i in range(len(chunk_2_lines))
        )

        # Target should be ~13,853 tokens per chunk
        target_chunk_size = total_tokens / expected_chunks

        # Chunks should be balanced (within 30% of target)
        max_variance = 0.3
        assert (
            abs(chunk_1_tokens - target_chunk_size) / target_chunk_size < max_variance
        )
        assert (
            abs(chunk_2_tokens - target_chunk_size) / target_chunk_size < max_variance
        )

        # Neither chunk should be < 70% of target (AC-5)
        min_threshold = 0.7
        assert chunk_1_tokens >= min_threshold * target_chunk_size
        assert chunk_2_tokens >= min_threshold * target_chunk_size

    # Trace: SPEC-BALANCED-CHUNKS-001, AC-7
    def test_balanced_single_chunk(self):
        """AC-7: When total tokens < max_token_length, create single chunk"""
        config = _build_config()
        with (
            patch(
                "src.core.streaming_translator.TranslationConfig", return_value=config
            ),
            patch("src.core.streaming_translator.OpenAI"),
        ):
            translator = StreamingTranslator(input_file="dummy", max_token_length=20000)

        lines = ["line1\n", "line2\n", "line3\n"]

        with patch.object(
            translator.token_counter,
            "count_tokens",
            side_effect=lambda text: len(text.splitlines()) * 1000,  # 3000 total
        ):
            chunks = list(translator.chunk_generator(lines))

        # Should create only 1 chunk since 3000 < 20000
        assert len(chunks) == 1
        assert chunks[0][0] == 1
        assert chunks[0][1] == "line1\nline2\nline3\n"

    # Trace: SPEC-BALANCED-CHUNKS-001, AC-6
    def test_balanced_oversized_line(self, caplog):
        """AC-6: Single line exceeding max_token_length is yielded standalone"""
        config = _build_config()
        with (
            patch(
                "src.core.streaming_translator.TranslationConfig", return_value=config
            ),
            patch("src.core.streaming_translator.OpenAI"),
        ):
            translator = StreamingTranslator(input_file="dummy", max_token_length=1000)

        lines = ["very long line\n", "normal line\n"]

        def count_tokens_mock(text):
            if "very long line" in text:
                return 5000  # Exceeds max
            return len(text.splitlines()) * 100

        with (
            patch.object(
                translator.token_counter,
                "count_tokens",
                side_effect=count_tokens_mock,
            ),
            caplog.at_level("WARNING"),
        ):
            chunks = list(translator.chunk_generator(lines))

        # Should create 2 chunks: oversized line alone, then normal line
        expected_chunks = 2
        assert len(chunks) == expected_chunks
        assert chunks[0] == (1, "very long line\n")
        assert chunks[1] == (2, "normal line\n")
        assert any("single line over limit" in message for message in caplog.messages)

    # Trace: SPEC-BALANCED-CHUNKS-001, AC-6 (edge case)
    def test_balanced_oversized_line_after_buffer(self, caplog):
        """AC-6 edge: Oversized line after buffered content yields with warning"""
        config = _build_config()
        with (
            patch(
                "src.core.streaming_translator.TranslationConfig", return_value=config
            ),
            patch("src.core.streaming_translator.OpenAI"),
        ):
            translator = StreamingTranslator(input_file="dummy", max_token_length=10000)

        # Scenario: buffer has 5000 tokens, then oversized line with 25000 tokens
        lines = ["normal1\n", "normal2\n", "oversized line\n", "normal3\n"]

        def count_tokens_mock(text):
            if "oversized line" in text:
                return 25000  # Exceeds max (10000)
            return len(text.splitlines()) * 2500  # Each normal line: 2500 tokens

        with (
            patch.object(
                translator.token_counter,
                "count_tokens",
                side_effect=count_tokens_mock,
            ),
            caplog.at_level("WARNING"),
        ):
            chunks = list(translator.chunk_generator(lines))

        # Should create 3 chunks:
        # 1. normal1+normal2 (5000 tokens)
        # 2. oversized line alone (25000 tokens) with warning
        # 3. normal3 (2500 tokens)
        expected_chunks = 3
        assert len(chunks) == expected_chunks

        # Verify no chunk exceeds max_token_length (except the warned oversized one)
        oversized_chunk_found = False
        for _chunk_idx, chunk_text in chunks:
            tokens = count_tokens_mock(chunk_text)
            if tokens > translator.max_token_length:
                # This should only happen for the oversized line chunk
                assert "oversized line" in chunk_text
                assert chunk_text.strip() == "oversized line"  # Should be standalone
                oversized_chunk_found = True

        assert oversized_chunk_found, "Oversized chunk should exist"
        assert any(
            "single line over limit" in message for message in caplog.messages
        ), "Warning should be logged for oversized line"

    # Trace: SPEC-BALANCED-CHUNKS-001, AC-3, AC-4
    def test_balanced_three_chunks(self):
        """Test balanced distribution with 3 chunks"""
        config = _build_config()
        with (
            patch(
                "src.core.streaming_translator.TranslationConfig", return_value=config
            ),
            patch("src.core.streaming_translator.OpenAI"),
        ):
            translator = StreamingTranslator(input_file="dummy", max_token_length=20000)

        # Simulate 45,000 tokens (should create 3 chunks of ~15,000 each)
        lines = [f"line{i}\n" for i in range(45)]

        with patch.object(
            translator.token_counter,
            "count_tokens",
            side_effect=lambda text: len(text.splitlines()) * 1000,
        ):
            chunks = list(translator.chunk_generator(lines))

        # Should create 3 chunks
        expected_chunks = 3
        assert len(chunks) == expected_chunks

        # Each chunk should have roughly 15 lines (15,000 tokens)
        target_lines_per_chunk = 15
        max_line_variance = 3
        for i, (_chunk_index, chunk_text) in enumerate(chunks):
            chunk_lines = len(chunk_text.strip().split("\n"))
            # Allow some variance but should be roughly balanced
            assert abs(chunk_lines - target_lines_per_chunk) <= max_line_variance, (
                f"Chunk {i + 1} has {chunk_lines} lines, "
                f"expected ~{target_lines_per_chunk}"
            )


# Trace: SPEC-REFACTOR-VALIDATION-001, TASK-20251228-REFACTOR-VALIDATION-001
class TestNoOpProgress:
    """Tests for NoOpProgress handler."""

    def test_noop_progress_update_does_not_raise(self):
        """AC-3: NoOp().update() returns None, does not raise"""
        noop = NoOpProgress()

        # Should not raise any exception
        noop.update()

        # Should accept all valid parameters
        noop.update(TaskID(1), completed=50, total=100, description="test")

    def test_noop_progress_add_task_returns_task_id(self):
        """NoOp.add_task() returns a TaskID without raising"""
        noop = NoOpProgress()
        task_id = noop.add_task("test task", total=100)

        # TaskID is a NewType wrapper around int, so it's just an int at runtime
        assert task_id is not None
        # Should return the dummy TaskID(0)
        assert task_id == 0


class TestProgressNoneHandling:
    """Tests for progress=None defensive handling."""

    def test_translate_chunk_accepts_progress_none(self):
        """AC-1: _translate_chunk() accepts progress=None without exception"""
        config = _build_config()
        with (
            patch(
                "src.core.streaming_translator.TranslationConfig", return_value=config
            ),
            patch("src.core.streaming_translator.OpenAI"),
        ):
            translator = StreamingTranslator(input_file="dummy")

        # Mock the API response
        mock_response = _create_streaming_response("번역된 텍스트")
        with patch.object(
            translator.client.chat.completions, "create", return_value=mock_response
        ):
            # Should not raise when progress=None
            result = translator._translate_chunk(
                chunk_index=1, chunk_text="Hello world", progress=None, task_id=None
            )

        assert result == "번역된 텍스트"

    def test_invoke_model_handles_progress_none(self):
        """AC-2: _invoke_model() handles progress=None, does not call update"""
        config = _build_config()
        with (
            patch(
                "src.core.streaming_translator.TranslationConfig", return_value=config
            ),
            patch("src.core.streaming_translator.OpenAI"),
        ):
            translator = StreamingTranslator(input_file="dummy")

        # Mock the API response
        mock_response = _create_streaming_response("번역 결과")
        with patch.object(
            translator.client.chat.completions, "create", return_value=mock_response
        ):
            # Should not raise AttributeError on None.update()
            result = translator._invoke_model(
                chunk_index=1, chunk_text="Test", progress=None, task_id=None
            )

        assert result == "번역 결과"

    def test_valid_progress_still_works(self):
        """AC-5: Valid Progress object still works as before"""
        config = _build_config()
        with (
            patch(
                "src.core.streaming_translator.TranslationConfig", return_value=config
            ),
            patch("src.core.streaming_translator.OpenAI"),
        ):
            translator = StreamingTranslator(input_file="dummy")

        # Create real Progress instance
        with Progress() as progress:
            task_id = progress.add_task("test", total=100)

            # Mock the API response
            mock_response = _create_streaming_response("번역 완료")
            with patch.object(
                translator.client.chat.completions,
                "create",
                return_value=mock_response,
            ):
                result = translator._invoke_model(
                    chunk_index=1,
                    chunk_text="Test text",
                    progress=progress,
                    task_id=task_id,
                )

            assert result == "번역 완료"
            # Progress should have been updated
            task = progress.tasks[0]
            assert task.completed > 0


# Trace: SPEC-REFACTOR-DEDUP-001, TASK-20251228-REFACTOR-DEDUP-001
class TestHelperMethods:
    """Tests for deduplicated helper methods."""

    def test_write_translations_creates_file_with_utf8(self, tmp_path):
        """AC-2: _write_translations() creates output file with UTF-8 encoding"""
        config = _build_config()
        with (
            patch(
                "src.core.streaming_translator.TranslationConfig", return_value=config
            ),
            patch("src.core.streaming_translator.OpenAI"),
        ):
            translator = StreamingTranslator(input_file="dummy")

        output_file = tmp_path / "output.txt"
        results = {1: "첫 번째", 2: "두 번째"}
        chunks = [(1, "chunk1"), (2, "chunk2")]

        translator._write_translations(results, chunks, str(output_file))

        # File should exist and be readable with UTF-8
        content = output_file.read_text(encoding="utf-8")
        assert "첫 번째" in content
        assert "두 번째" in content

    def test_write_translations_correct_formatting(self, tmp_path):
        """AC-1: _write_translations() writes with double newline between chunks"""
        config = _build_config()
        with (
            patch(
                "src.core.streaming_translator.TranslationConfig", return_value=config
            ),
            patch("src.core.streaming_translator.OpenAI"),
        ):
            translator = StreamingTranslator(input_file="dummy")

        output_file = tmp_path / "output.txt"
        results = {1: "first", 2: "second", 3: "third"}
        chunks = [(1, "c1"), (2, "c2"), (3, "c3")]

        translator._write_translations(results, chunks, str(output_file))

        content = output_file.read_text(encoding="utf-8")
        # Should have exactly 5 newlines: first\n\nsecond\n\nthird\n\n
        # That's 3 chunks * 2 newlines each = 6 newlines total
        assert content == "first\n\nsecond\n\nthird\n\n"

    def test_write_translations_skips_missing_chunks(self, tmp_path):
        """_write_translations() only writes chunks that were successfully translated"""
        config = _build_config()
        with (
            patch(
                "src.core.streaming_translator.TranslationConfig", return_value=config
            ),
            patch("src.core.streaming_translator.OpenAI"),
        ):
            translator = StreamingTranslator(input_file="dummy")

        output_file = tmp_path / "output.txt"
        # Chunk 2 is missing (failed translation)
        results = {1: "first", 3: "third"}
        chunks = [(1, "c1"), (2, "c2"), (3, "c3")]

        translator._write_translations(results, chunks, str(output_file))

        content = output_file.read_text(encoding="utf-8")
        # Should only have chunks 1 and 3
        assert content == "first\n\nthird\n\n"
        assert "second" not in content

    def test_update_task_progress_success(self):
        """AC-3: _update_task_progress() marks success correctly"""
        config = _build_config()
        with (
            patch(
                "src.core.streaming_translator.TranslationConfig", return_value=config
            ),
            patch("src.core.streaming_translator.OpenAI"),
        ):
            translator = StreamingTranslator(input_file="dummy")

        with Progress() as progress:
            chunk_task = progress.add_task("Test chunk", total=100)

            translator._update_task_progress(
                success=True, chunk_index=1, progress=progress, task_id=chunk_task
            )

            # Task should be marked as complete and hidden
            task = progress.tasks[0]
            # 100 is the total we set when adding the task
            assert task.completed == task.total
            assert not task.visible

    def test_update_task_progress_failure(self):
        """AC-4: _update_task_progress() marks failure correctly"""
        config = _build_config()
        with (
            patch(
                "src.core.streaming_translator.TranslationConfig", return_value=config
            ),
            patch("src.core.streaming_translator.OpenAI"),
        ):
            translator = StreamingTranslator(input_file="dummy")

        with Progress() as progress:
            chunk_task = progress.add_task("Test chunk", total=100)

            translator._update_task_progress(
                success=False, chunk_index=1, progress=progress, task_id=chunk_task
            )

            # Task should be marked as failed and hidden
            task = progress.tasks[0]
            assert "(failed)" in task.description
            assert not task.visible

    def test_identical_output_sequential_parallel(self, tmp_path):
        """AC-5: Both paths produce identical file output"""
        input_file = tmp_path / "input.txt"
        seq_output = tmp_path / "seq_output.txt"
        par_output = tmp_path / "par_output.txt"

        # Create test input
        input_file.write_text("line1\nline2\nline3\n")

        config = _build_config()

        # Sequential translation
        with (
            patch(
                "src.core.streaming_translator.TranslationConfig", return_value=config
            ),
            patch("src.core.streaming_translator.OpenAI"),
        ):
            seq_translator = StreamingTranslator(
                input_file=str(input_file),
                output_file=str(seq_output),
                max_token_length=5,
                max_workers=1,
            )

        # Parallel translation
        with (
            patch(
                "src.core.streaming_translator.TranslationConfig", return_value=config
            ),
            patch("src.core.streaming_translator.OpenAI"),
        ):
            par_translator = StreamingTranslator(
                input_file=str(input_file),
                output_file=str(par_output),
                max_token_length=5,
                max_workers=3,
            )

        # Mock translation to return deterministic results
        def fake_translate(
            chunk_index: int, _chunk_text: str, _progress=None, _task_id=None
        ):
            return f"translated_chunk_{chunk_index}"

        with (
            patch.object(
                seq_translator.token_counter,
                "count_tokens",
                side_effect=lambda text: len(text.splitlines()) * 5,
            ),
            patch.object(
                seq_translator, "_translate_chunk", side_effect=fake_translate
            ),
        ):
            seq_translator.translate()

        with (
            patch.object(
                par_translator.token_counter,
                "count_tokens",
                side_effect=lambda text: len(text.splitlines()) * 5,
            ),
            patch.object(
                par_translator, "_translate_chunk", side_effect=fake_translate
            ),
        ):
            par_translator.translate()

        # Files should be byte-for-byte identical
        seq_content = seq_output.read_bytes()
        par_content = par_output.read_bytes()
        assert seq_content == par_content
