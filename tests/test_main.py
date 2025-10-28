# Test main entry point

from unittest.mock import MagicMock, patch

from src.main import main


class TestMain:
    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"})
    @patch("src.main.TextPreprocessor")
    @patch("src.main.StreamingTranslator")
    def test_main_success_flow(self, mock_translator_class, mock_preprocessor_class):
        """Test successful main execution flow"""
        # Given
        mock_preprocessor = MagicMock()
        mock_preprocessor_class.return_value = mock_preprocessor

        mock_translator = MagicMock()
        mock_translator_class.return_value = mock_translator

        # When
        main()

        # Then
        mock_preprocessor_class.assert_called_once()
        mock_preprocessor.run.assert_called_once()
        mock_translator_class.assert_called_once_with(input_file="_trimmed_text.txt")
        mock_translator.translate.assert_called_once()
        mock_translator.format_output.assert_called_once()

    @patch.dict("os.environ", {}, clear=True)
    @patch("src.main.TextPreprocessor")
    @patch("sys.exit")
    @patch("src.main.logger")
    def test_main_missing_api_key(
        self, mock_logger, mock_exit, _mock_preprocessor_class
    ):
        """Test main with missing API key"""
        # When
        main()

        # Then
        mock_logger.error.assert_called()
        mock_exit.assert_called_with(1)

    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"})
    @patch("src.main.TextPreprocessor")
    @patch("src.main.StreamingTranslator")
    @patch("src.main.logger")
    @patch("sys.exit")
    def test_main_translation_error(
        self, mock_exit, mock_logger, mock_translator_class, mock_preprocessor_class
    ):
        """Test main with translation error"""
        # Given
        mock_preprocessor = MagicMock()
        mock_preprocessor_class.return_value = mock_preprocessor

        mock_translator = MagicMock()
        mock_translator.translate.side_effect = Exception("Translation failed")
        mock_translator_class.return_value = mock_translator

        # When
        main()

        # Then
        mock_logger.exception.assert_called()
        mock_exit.assert_called_once_with(1)
