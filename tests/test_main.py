# GENERATED FROM SPEC-CLI-EXIT-001

# Test main entry point

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from src.main import main


class TestMain:
    # Trace: SPEC-CLI-EXIT-001, TEST-CLI-EXIT-001-AC1
    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"})
    @patch("src.main.TextPreprocessor")
    @patch("src.main.StreamingTranslator")
    @patch("sys.exit")
    def test_main_success_flow(
        self, mock_exit, mock_translator_class, mock_preprocessor_class
    ):
        """Test successful main execution flow with metrics surfaced"""
        mock_preprocessor = MagicMock()
        mock_preprocessor_class.return_value = mock_preprocessor

        mock_translator = MagicMock()
        mock_translator.translate.return_value = SimpleNamespace(
            successes=3, failures=0, duration_seconds=1.23
        )
        mock_translator_class.return_value = mock_translator

        main()

        mock_preprocessor_class.assert_called_once()
        mock_preprocessor.run.assert_called_once()
        mock_translator_class.assert_called_once_with(input_file="_trimmed_text.txt")
        mock_translator.translate.assert_called_once()
        mock_translator.format_output.assert_called_once()
        mock_exit.assert_not_called()

    # Trace: SPEC-CLI-EXIT-001, TEST-CLI-EXIT-001-AC2
    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"})
    @patch("src.main.TextPreprocessor")
    @patch("src.main.StreamingTranslator")
    @patch("src.main.logger")
    @patch("sys.exit")
    def test_main_partial_failures_warns(
        self,
        mock_exit,
        mock_logger,
        mock_translator_class,
        mock_preprocessor_class,
    ):
        """Warn when some chunks fail"""
        mock_preprocessor = MagicMock()
        mock_preprocessor_class.return_value = mock_preprocessor

        mock_translator = MagicMock()
        mock_translator.translate.return_value = SimpleNamespace(
            successes=2, failures=1, duration_seconds=2.5
        )
        mock_translator_class.return_value = mock_translator

        main()

        mock_logger.warning.assert_any_call(
            "일부 번역 청크가 실패했습니다. 로그를 확인하고 재시도를 고려하세요."
        )
        mock_exit.assert_called_once_with(2)

    # Trace: SPEC-CLI-EXIT-001, TEST-CLI-EXIT-001-AC3
    @patch.dict("os.environ", {}, clear=True)
    @patch("src.main.TextPreprocessor")
    @patch("sys.exit")
    @patch("src.main.logger")
    def test_main_missing_api_key(
        self, mock_logger, mock_exit, _mock_preprocessor_class
    ):
        """Test main with missing API key"""
        main()

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
        mock_preprocessor = MagicMock()
        mock_preprocessor_class.return_value = mock_preprocessor

        mock_translator = MagicMock()
        mock_translator.translate.side_effect = Exception("Translation failed")
        mock_translator_class.return_value = mock_translator

        main()

        mock_logger.exception.assert_called()
        mock_exit.assert_called_once_with(1)
