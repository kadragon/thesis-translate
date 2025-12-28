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
    @patch("pathlib.Path.exists", return_value=False)
    def test_main_success_flow(
        self,
        _mock_path_exists,
        mock_exit,
        mock_translator_class,
        mock_preprocessor_class,
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
    @patch("pathlib.Path.exists", return_value=False)
    def test_main_partial_failures_warns(
        self,
        _mock_path_exists,
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
    @patch("pathlib.Path.exists", return_value=False)
    def test_main_missing_api_key(
        self, _mock_path_exists, mock_logger, mock_exit, _mock_preprocessor_class
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
    @patch("pathlib.Path.exists", return_value=False)
    def test_main_translation_error(
        self,
        _mock_path_exists,
        mock_exit,
        mock_logger,
        mock_translator_class,
        mock_preprocessor_class,
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

    # Test to exercise sys.exit(1) without mocking it
    @patch.dict("os.environ", {}, clear=True)
    @patch("src.main.TextPreprocessor")
    @patch("pathlib.Path.exists", return_value=False)
    def test_main_missing_api_key_exit_code(
        self, _mock_path_exists, _mock_preprocessor_class
    ):
        """Test that missing API key causes actual exit(1)"""
        # This test verifies sys.exit(1) is called (line 63)
        with __import__("pytest").raises(SystemExit) as exc_info:
            main()

        assert exc_info.value.code == 1

    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"})
    @patch("src.main.TextPreprocessor")
    @patch("src.main.StreamingTranslator")
    @patch("src.main.confirm_clear_file", return_value=True)
    @patch("src.main.logger")
    def test_main_clears_non_empty_file_when_user_confirms(
        self,
        mock_logger,
        mock_confirm,
        mock_translator_class,
        mock_preprocessor_class,
        tmp_path,
    ):
        """Test that non-empty input file is cleared when user confirms"""
        # Create a non-empty input file
        input_file = tmp_path / "test_input.txt"
        input_file.write_text("existing content", encoding="UTF-8")

        mock_preprocessor = MagicMock()
        mock_preprocessor_class.return_value = mock_preprocessor

        mock_translator = MagicMock()
        mock_translator.translate.return_value = SimpleNamespace(
            successes=1, failures=0, duration_seconds=1.0
        )
        mock_translator_class.return_value = mock_translator

        with patch("src.config.INPUT_FILE", str(input_file)):
            main()

        # File should be cleared
        assert input_file.read_text(encoding="UTF-8") == ""
        mock_logger.info.assert_any_call("✅ 입력 파일이 초기화되었습니다.")
        mock_confirm.assert_called_once_with(str(input_file))

    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"})
    @patch("src.main.TextPreprocessor")
    @patch("src.main.StreamingTranslator")
    @patch("src.main.confirm_clear_file", return_value=False)
    def test_main_keeps_non_empty_file_when_user_declines(
        self, mock_confirm, mock_translator_class, mock_preprocessor_class, tmp_path
    ):
        """Test that non-empty input file is kept when user declines"""
        # Create a non-empty input file
        input_file = tmp_path / "test_input.txt"
        original_content = "existing content"
        input_file.write_text(original_content, encoding="UTF-8")

        mock_preprocessor = MagicMock()
        mock_preprocessor_class.return_value = mock_preprocessor

        mock_translator = MagicMock()
        mock_translator.translate.return_value = SimpleNamespace(
            successes=1, failures=0, duration_seconds=1.0
        )
        mock_translator_class.return_value = mock_translator

        with patch("src.config.INPUT_FILE", str(input_file)):
            main()

        # File should keep original content
        assert input_file.read_text(encoding="UTF-8") == original_content
        mock_confirm.assert_called_once_with(str(input_file))

    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"})
    @patch("src.main.TextPreprocessor")
    @patch("src.main.StreamingTranslator")
    @patch("src.main.confirm_clear_file")
    def test_main_skips_prompt_for_empty_file(
        self, mock_confirm, mock_translator_class, mock_preprocessor_class, tmp_path
    ):
        """Test that empty input file doesn't trigger prompt"""
        # Create an empty input file
        input_file = tmp_path / "test_input.txt"
        input_file.write_text("", encoding="UTF-8")

        mock_preprocessor = MagicMock()
        mock_preprocessor_class.return_value = mock_preprocessor

        mock_translator = MagicMock()
        mock_translator.translate.return_value = SimpleNamespace(
            successes=1, failures=0, duration_seconds=1.0
        )
        mock_translator_class.return_value = mock_translator

        with patch("src.config.INPUT_FILE", str(input_file)):
            main()

        # confirm_clear_file should not be called for empty file
        mock_confirm.assert_not_called()

    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"})
    @patch("src.main.TextPreprocessor")
    @patch("src.main.StreamingTranslator")
    @patch("src.main.confirm_clear_file")
    def test_main_skips_prompt_for_nonexistent_file(
        self, mock_confirm, mock_translator_class, mock_preprocessor_class, tmp_path
    ):
        """Test that nonexistent input file doesn't trigger prompt"""
        # Use a path that doesn't exist
        input_file = tmp_path / "nonexistent.txt"

        mock_preprocessor = MagicMock()
        mock_preprocessor_class.return_value = mock_preprocessor

        mock_translator = MagicMock()
        mock_translator.translate.return_value = SimpleNamespace(
            successes=1, failures=0, duration_seconds=1.0
        )
        mock_translator_class.return_value = mock_translator

        with patch("src.config.INPUT_FILE", str(input_file)):
            main()

        # confirm_clear_file should not be called for nonexistent file
        mock_confirm.assert_not_called()
