# GENERATED FROM SPEC-TEXT-PREP-001

import pytest
from unittest.mock import patch, mock_open
from pathlib import Path

from src.utils.text_preprocessor import TextPreprocessor


class TestTextPreprocessor:
    def test_init(self):
        """Test initialization"""
        # When
        preprocessor = TextPreprocessor()

        # Then
        assert preprocessor.text == ""
        assert preprocessor.page_number is None

    @patch('src.utils.text_preprocessor.clipboard.paste')
    def test_add_text_from_clipboard(self, mock_paste):
        """AC-2: GIVEN text in clipboard WHEN adding text THEN text is appended to internal buffer"""
        # Given
        mock_paste.return_value = "Hello world"
        preprocessor = TextPreprocessor()

        # When
        preprocessor.add_text_from_clipboard()

        # Then
        assert preprocessor.text == "Hello world\n"

    @patch('builtins.print')
    def test_clean_text(self, mock_print):
        """AC-3: GIVEN accumulated text WHEN cleaning text THEN lines are merged and hyphens removed"""
        # Given
        preprocessor = TextPreprocessor()
        preprocessor.text = "Hello -\nworld\n  test  "

        # When
        preprocessor._clean_text()

        # Then
        assert preprocessor.text == "Hello world test"

    @patch('pathlib.Path.open', new_callable=mock_open)
    def test_add_text_to_file(self, mock_file):
        """AC-4: GIVEN cleaned text WHEN saving to file THEN text is appended with proper spacing"""
        # Given
        preprocessor = TextPreprocessor()

        # When
        preprocessor.add_text_to_file("Hello world")

        # Then
        mock_file.assert_called_with("a", encoding="UTF-8")
        mock_file().write.assert_called_with("  Hello world\n\n")

    @patch('builtins.input')
    @patch('src.utils.text_preprocessor.clipboard.paste')
    @patch('builtins.print')
    def test_run_add_text_flow(self, mock_print, mock_paste, mock_input):
        """Test the main run loop for adding text"""
        # Given
        mock_input.side_effect = ["123", "A", "world", "B"]  # page, command A, text input, quit
        mock_paste.return_value = "Hello"
        preprocessor = TextPreprocessor()

        # When
        preprocessor.run()

        # Then
        assert preprocessor.page_number == 123
        assert "Hello\n" in preprocessor.text

    @patch('builtins.input')
    @patch('src.utils.text_preprocessor.clipboard.paste')
    @patch('builtins.print')
    @patch('pathlib.Path.open', new_callable=mock_open)
    def test_run_translate_flow(self, mock_file, mock_print, mock_paste, mock_input):
        """Test the main run loop for translating text"""
        # Given
        mock_input.side_effect = ["123", "", "world", "B"]  # page, empty command (translate), text input, quit
        mock_paste.return_value = "Hello"
        preprocessor = TextPreprocessor()

        # When
        preprocessor.run()

        # Then
        assert preprocessor.page_number == 123
        # Should have called add_text_to_file
        assert mock_file.called
