# GENERATED FROM SPEC-TRANSLATION-001

from unittest.mock import Mock, patch

import pytest

from src.core.streaming_translator import StreamingTranslator


class TestTranslator:
    @patch("src.core.streaming_translator.OpenAI")
    def test_translate_chunk_success(self, mock_openai_class):
        """AC-2: GIVEN text chunk WHEN translating THEN OpenAI API is called with
        prompt template"""
        # Given
        mock_client = Mock()
        mock_openai_class.return_value = mock_client
        mock_response = Mock()
        mock_choice = Mock()
        mock_choice.message.content = "번역된 텍스트"
        mock_response.choices = [mock_choice]
        mock_client.chat.completions.create.return_value = mock_response

        config = Mock()
        config.PROMPT_TEMPLATE = "Translate: {text}"
        config.glossary = "glossary"
        config.model = "gpt-4"
        config.temperature = 0.5
        with patch(
            "src.core.streaming_translator.TranslationConfig", return_value=config
        ):
            translator = StreamingTranslator(input_file="dummy")

        # When
        result = translator._translate_chunk("Hello world")

        # Then
        assert result == "번역된 텍스트"
        mock_client.chat.completions.create.assert_called_once()

    @patch("src.core.streaming_translator.OpenAI")
    def test_translate_chunk_api_error(self, mock_openai_class):
        """Test handling of API errors"""
        # Given
        mock_client = Mock()
        mock_openai_class.return_value = mock_client
        mock_client.chat.completions.create.side_effect = Exception("API Error")

        config = Mock()
        with patch(
            "src.core.streaming_translator.TranslationConfig", return_value=config
        ):
            translator = StreamingTranslator(input_file="dummy")

        # When
        result = translator._translate_chunk("Hello world")

        # Then
        assert result == ""

    def test_translate_file_not_found(self):
        """Test handling of missing input file"""
        # Given
        config = Mock()
        with patch(
            "src.core.streaming_translator.TranslationConfig", return_value=config
        ):
            translator = StreamingTranslator(input_file="nonexistent.txt")

        # When/Then
        with pytest.raises(FileNotFoundError):
            translator.translate()

    @patch("src.core.streaming_translator.OpenAI")
    def test_translate_success(self, mock_openai_class, tmp_path):
        """AC-1 & AC-3: GIVEN input file WHEN translating THEN text is split into
        chunks and translated"""
        # Given
        input_file = tmp_path / "input.txt"
        output_file = tmp_path / "output.txt"
        input_file.write_text("Short text for translation.")

        mock_client = Mock()
        mock_openai_class.return_value = mock_client
        mock_response = Mock()
        mock_choice = Mock()
        mock_choice.message.content = "번역 결과"
        mock_response.choices = [mock_choice]
        mock_client.chat.completions.create.return_value = mock_response

        config = Mock()
        config.PROMPT_TEMPLATE = "Translate: {text}"
        config.glossary = ""
        config.model = "gpt-4"
        config.temperature = 0.5
        with patch(
            "src.core.streaming_translator.TranslationConfig", return_value=config
        ):
            translator = StreamingTranslator(
                input_file=str(input_file), output_file=str(output_file)
            )

        # When
        translator.translate()

        # Then
        assert output_file.exists()
        content = output_file.read_text()
        assert "번역 결과" in content

    def test_format_output(self, tmp_path):
        """AC-4: GIVEN output file WHEN formatting THEN lines are indented properly"""
        # Given
        output_file = tmp_path / "output.txt"
        output_file.write_text("Line 1\n\nLine 2\n  Already indented\n")

        config = Mock()
        with patch(
            "src.core.streaming_translator.TranslationConfig", return_value=config
        ):
            translator = StreamingTranslator(
                input_file="dummy", output_file=str(output_file)
            )

        # When
        translator.format_output()

        # Then
        content = output_file.read_text()
        lines = content.split("\n")
        assert lines[0] == "  Line 1"
        assert lines[1] == ""
        assert lines[2] == "  Line 2"
        assert lines[3] == "  Already indented"
