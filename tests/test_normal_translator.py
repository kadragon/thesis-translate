# GENERATED FROM SPEC-TRANSLATION-001

from unittest.mock import Mock, patch

import pytest

from src.core.streaming_translator import (
    PermanentTranslationError,
    StreamingTranslator,
    TransientTranslationError,
    TranslationRunResult,
)


def _build_config(prompt: str = "Translate: {text}") -> Mock:
    config = Mock()
    config.PROMPT_TEMPLATE = prompt
    config.glossary = "glossary"
    config.model = "gpt-4"
    config.temperature = 0.5
    return config


class TestTranslator:
    # Trace: SPEC-TRANSLATION-001, TEST-TRANSLATION-001-AC2
    def test_chunk_generator_deterministic(self):
        """AC-2: chunk generator yields deterministic order"""
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

        assert chunks == [
            (1, "first\nsecond\n"),
            (2, "third\n"),
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
        mock_invoke.assert_called_once_with(1, "Hello world")

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
            TransientTranslationError("temporary"),
            "성공!",
        ]
        expected_calls = len(responses)

        def fake_invoke(_chunk_index: int, _chunk_text: str):
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
                side_effect=TransientTranslationError("still failing"),
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
        mock_client.chat.completions.create.return_value = Mock(
            choices=[Mock(message=Mock(content="번역 결과"))]
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
            PermanentTranslationError("fatal"),
        ]

        def fake_invoke(_chunk_index: int, _chunk_text: str):
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
