# GENERATED FROM SPEC-TEXT-PREP-001

from typing import cast
from unittest.mock import mock_open, patch

from src.utils.text_preprocessor import TextPreprocessor

TEST_PAGE_NUMBER = 123
CLIPBOARD_ERROR = RuntimeError("Clipboard error")


class TestTextPreprocessor:
    def test_init(self):
        """Test initialization"""
        # When
        preprocessor = TextPreprocessor()

        # Then
        assert preprocessor.text == ""
        assert preprocessor.page_number is None

    # Trace: SPEC-TEXT-PREP-001, TEST-TEXT-PREP-001-AC2
    @patch("src.utils.text_preprocessor.clipboard.paste")
    def test_add_text_from_clipboard(self, mock_paste):
        """AC-2: GIVEN text in clipboard WHEN adding text THEN text is appended to
        internal buffer"""
        # Given
        mock_paste.return_value = "Hello world"
        preprocessor = TextPreprocessor()

        # When
        preprocessor.add_text_from_clipboard()

        # Then
        assert preprocessor.text == "Hello world\n"

    # Trace: SPEC-TEXT-PREP-001, TEST-TEXT-PREP-001-AC3
    def test_clean_text(self):
        """AC-3: GIVEN accumulated text WHEN cleaning text THEN lines are merged and
        hyphens removed"""
        # Given
        preprocessor = TextPreprocessor()
        preprocessor.text = "Hello -\nworld\n  test  "

        # When
        preprocessor._clean_text()

        # Then
        assert preprocessor.text == "Hello world test"

    # Trace: SPEC-TEXT-PREP-001, TEST-TEXT-PREP-001-AC4
    @patch("pathlib.Path.open", new_callable=mock_open)
    def test_add_text_to_file(self, mock_file):
        """AC-4: GIVEN cleaned text WHEN saving to file THEN text is appended with
        proper spacing"""
        # Given
        preprocessor = TextPreprocessor()

        # When
        preprocessor.add_text_to_file("Hello world")

        # Then
        mock_file.assert_called_with("a", encoding="UTF-8")
        mock_file().write.assert_called_with("  Hello world\n\n")

    # Trace: SPEC-TEXT-PREP-001, TEST-TEXT-PREP-001-AC1
    @patch("src.utils.text_preprocessor.ask_menu_action")
    @patch("src.utils.text_preprocessor.ask_start_page")
    @patch("src.utils.text_preprocessor.clipboard.paste")
    def test_run_add_text_flow(self, mock_paste, mock_start_page, mock_menu_action):
        """Test the main run loop for adding text"""
        # Given
        mock_start_page.return_value = TEST_PAGE_NUMBER
        mock_menu_action.side_effect = ["A", "B"]  # Add text, then quit
        mock_paste.return_value = "Hello"
        preprocessor = TextPreprocessor()

        # When
        preprocessor.run()

        # Then
        assert preprocessor.page_number == TEST_PAGE_NUMBER
        assert "Hello\n" in preprocessor.text

    # Trace: SPEC-TEXT-PREP-001, TEST-TEXT-PREP-001-AC4
    @patch("src.utils.text_preprocessor.ask_menu_action")
    @patch("src.utils.text_preprocessor.ask_start_page")
    @patch("src.utils.text_preprocessor.clipboard.paste")
    @patch("pathlib.Path.open", new_callable=mock_open)
    def test_run_translate_flow(
        self, mock_file, mock_paste, mock_start_page, mock_menu_action
    ):
        """Test the main run loop for translating text"""
        # Given
        mock_start_page.return_value = TEST_PAGE_NUMBER
        mock_menu_action.side_effect = ["", "B"]  # Empty (translate), then quit
        mock_paste.return_value = "Hello"
        preprocessor = TextPreprocessor()

        # When
        preprocessor.run()

        # Then
        assert preprocessor.page_number == TEST_PAGE_NUMBER
        # Should have called add_text_to_file
        assert mock_file.called
        mock_file().write.assert_called_with("  Hello\n\n")

    # Trace: SPEC-TEXT-PREP-001, TEST-TEXT-PREP-001-AC5
    @patch("src.utils.text_preprocessor.ask_menu_action")
    @patch("src.utils.text_preprocessor.ask_start_page")
    @patch("src.utils.text_preprocessor.clipboard.paste")
    @patch("pathlib.Path.open", new_callable=mock_open)
    def test_run_translate_clean_flow(
        self, mock_file, mock_paste, mock_start_page, mock_menu_action
    ):
        """AC-5: GIVEN command C WHEN invoked THEN cleaned text writes once"""
        # Given
        mock_start_page.return_value = TEST_PAGE_NUMBER
        mock_menu_action.side_effect = ["C", "B"]  # Clean, then quit
        mock_paste.return_value = "Hello\nworld"
        preprocessor = TextPreprocessor()

        # When
        preprocessor.run()

        # Then
        assert preprocessor.page_number == TEST_PAGE_NUMBER
        write_calls = [call.args[0] for call in mock_file().write.call_args_list]
        assert write_calls[0] == "  Hello world\n\n"

    # Trace: SPEC-TEXT-PREP-001, TEST-TEXT-PREP-001-AC6
    @patch("src.utils.text_preprocessor.logger")
    @patch(
        "src.utils.text_preprocessor.clipboard.paste",
        side_effect=CLIPBOARD_ERROR,
    )
    def test_add_text_from_clipboard_error(self, _mock_paste, mock_logger):
        """AC-6: GIVEN clipboard failure WHEN adding text THEN warning issued"""
        # Given
        preprocessor = TextPreprocessor()

        # When
        preprocessor.add_text_from_clipboard()

        # Then
        mock_logger.warning.assert_called_once()
        assert preprocessor.text == ""
        warning_message = mock_logger.warning.call_args[0][0]
        assert "클립보드" in warning_message

    # Trace: SPEC-TEXT-PREP-001, TEST-TEXT-PREP-001-AC7
    @patch("src.utils.text_preprocessor.logger")
    def test_clean_text_error(self, mock_logger):
        """AC-7: GIVEN cleaning failure WHEN normalising text THEN buffer preserved"""
        # Given
        preprocessor = TextPreprocessor()

        class FaultyText:
            def split(self, _separator):
                error_message = "boom"
                raise ValueError(error_message)

        preprocessor.text = cast("str", FaultyText())

        # When
        preprocessor._clean_text()

        # Then
        mock_logger.warning.assert_called_once()
        assert isinstance(preprocessor.text, FaultyText)
        warning_message = mock_logger.warning.call_args[0][0]
        assert "텍스트 정리" in warning_message

    @patch("src.utils.text_preprocessor.ask_menu_action")
    @patch("src.utils.text_preprocessor.ask_start_page")
    @patch("pathlib.Path.open", new_callable=mock_open)
    def test_run_page_number_addition(
        self, mock_file, mock_start_page, mock_menu_action
    ):
        """Test that 'E' command adds page number and increments counter"""
        # Given
        initial_page = 100
        expected_final_page = 102  # Started at 100, incremented twice

        mock_start_page.return_value = initial_page
        mock_menu_action.side_effect = ["E", "E", "B"]  # Add page twice, then quit
        preprocessor = TextPreprocessor()

        # When
        preprocessor.run()

        # Then
        assert preprocessor.page_number == expected_final_page
        write_calls = [call.args[0] for call in mock_file().write.call_args_list]
        assert write_calls == ["  p.100\n\n", "  p.101\n\n"]

    @patch("src.utils.text_preprocessor.ask_menu_action")
    @patch("src.utils.text_preprocessor.ask_start_page")
    def test_run_invalid_page_number_retry(self, mock_start_page, mock_menu_action):
        """Test that page number is set from ask_start_page"""
        # Given
        valid_page_number = 42

        # ask_start_page handles validation internally via rich.prompt.IntPrompt
        mock_start_page.return_value = valid_page_number
        mock_menu_action.side_effect = ["B"]  # Quit immediately
        preprocessor = TextPreprocessor()

        # When
        preprocessor.run()

        # Then
        assert preprocessor.page_number == valid_page_number
        mock_start_page.assert_called_once()
