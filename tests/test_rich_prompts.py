"""Tests for rich-based interactive prompts."""

from unittest.mock import patch

from src.utils.rich_prompts import ask_menu_action, ask_start_page, confirm_clear_file

TEST_PAGE_NUMBER = 42


class TestRichPrompts:
    @patch("src.utils.rich_prompts.Confirm.ask", return_value=True)
    @patch("src.utils.rich_prompts.console")
    def test_confirm_clear_file_user_confirms(self, mock_console, mock_confirm_ask):
        """Test that confirm_clear_file returns True when user confirms"""
        # When
        result = confirm_clear_file("test_file.txt")

        # Then
        assert result is True
        mock_confirm_ask.assert_called_once()
        mock_console.print.assert_called()

    @patch("src.utils.rich_prompts.Confirm.ask", return_value=False)
    @patch("src.utils.rich_prompts.console")
    def test_confirm_clear_file_user_declines(self, mock_console, mock_confirm_ask):
        """Test that confirm_clear_file returns False when user declines"""
        # When
        result = confirm_clear_file("test_file.txt")

        # Then
        assert result is False
        mock_confirm_ask.assert_called_once()
        mock_console.print.assert_called()

    @patch("src.utils.rich_prompts.IntPrompt.ask", return_value=TEST_PAGE_NUMBER)
    @patch("src.utils.rich_prompts.console")
    def test_ask_start_page(self, mock_console, mock_int_prompt_ask):
        """Test that ask_start_page returns page number from IntPrompt"""
        # When
        result = ask_start_page()

        # Then
        assert result == TEST_PAGE_NUMBER
        mock_int_prompt_ask.assert_called_once()
        mock_console.print.assert_called()

    @patch("src.utils.rich_prompts.Prompt.ask", return_value="A")
    @patch("src.utils.rich_prompts.console")
    def test_ask_menu_action_add(self, mock_console, mock_prompt_ask):
        """Test that ask_menu_action returns 'A' for add text"""
        # When
        result = ask_menu_action()

        # Then
        assert result == "A"
        mock_prompt_ask.assert_called_once()
        mock_console.print.assert_called()

    @patch("src.utils.rich_prompts.Prompt.ask", return_value="")
    @patch("src.utils.rich_prompts.console")
    def test_ask_menu_action_proceed(self, mock_console, mock_prompt_ask):
        """Test that ask_menu_action returns '' for proceed"""
        # When
        result = ask_menu_action()

        # Then
        assert result == ""
        mock_prompt_ask.assert_called_once()
        mock_console.print.assert_called()

    @patch("src.utils.rich_prompts.Prompt.ask", return_value="E")
    @patch("src.utils.rich_prompts.console")
    def test_ask_menu_action_page_number(self, mock_console, mock_prompt_ask):
        """Test that ask_menu_action returns 'E' for add page number"""
        # When
        result = ask_menu_action()

        # Then
        assert result == "E"
        mock_prompt_ask.assert_called_once()
        mock_console.print.assert_called()

    @patch("src.utils.rich_prompts.Prompt.ask", return_value="B")
    @patch("src.utils.rich_prompts.console")
    def test_ask_menu_action_quit(self, mock_console, mock_prompt_ask):
        """Test that ask_menu_action returns 'B' for quit"""
        # When
        result = ask_menu_action()

        # Then
        assert result == "B"
        mock_prompt_ask.assert_called_once()
        mock_console.print.assert_called()
