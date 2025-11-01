"""Integration tests for TextPreprocessor with ConcurrentOrchestrator.

Trace: SPEC-USER-PROMPTED-001, TEST-USER-PROMPTED-001-AC2
Trace: SPEC-USER-PROMPTED-001, TEST-USER-PROMPTED-001-AC3
Trace: SPEC-USER-PROMPTED-001, TEST-USER-PROMPTED-001-AC6
"""

from unittest.mock import MagicMock, patch

from src.utils.text_preprocessor import TextPreprocessor


class TestTextPreprocessorIntegration:
    """Integration tests for TextPreprocessor with orchestrator."""

    # Trace: SPEC-USER-PROMPTED-001, TEST-USER-PROMPTED-001-AC2
    def test_display_translation_status_when_ready(self) -> None:
        """Test that translation status is displayed when ready."""
        # Create mock orchestrator
        mock_orchestrator = MagicMock()
        mock_orchestrator.is_translation_ready.return_value = (True, 45000)

        preprocessor = TextPreprocessor(orchestrator=mock_orchestrator)

        # Get translation status
        status = preprocessor._display_translation_status()

        # Verify status message includes token count
        assert "T:번역시작" in status
        assert "45000 tokens" in status

    def test_display_translation_status_when_not_ready(self) -> None:
        """Test that no status is displayed when translation not ready."""
        mock_orchestrator = MagicMock()
        mock_orchestrator.is_translation_ready.return_value = (False, 20000)

        preprocessor = TextPreprocessor(orchestrator=mock_orchestrator)

        status = preprocessor._display_translation_status()

        # Verify empty status when not ready
        assert status == ""

    def test_display_translation_status_without_orchestrator(self) -> None:
        """Test that no status is displayed without orchestrator."""
        preprocessor = TextPreprocessor(orchestrator=None)

        status = preprocessor._display_translation_status()

        assert status == ""

    # Trace: SPEC-USER-PROMPTED-001, TEST-USER-PROMPTED-001-AC3
    @patch("builtins.print")
    def test_handle_translation_trigger_success(self, mock_print: MagicMock) -> None:
        """Test successful translation trigger."""
        mock_orchestrator = MagicMock()
        mock_orchestrator.trigger_translation_manual.return_value = True

        preprocessor = TextPreprocessor(orchestrator=mock_orchestrator)

        # Trigger translation
        result = preprocessor._handle_translation_trigger()

        assert result is True
        mock_orchestrator.trigger_translation_manual.assert_called_once()
        mock_print.assert_called_once_with("번역을 시작합니다...")

    @patch("builtins.print")
    def test_handle_translation_trigger_not_ready(self, mock_print: MagicMock) -> None:
        """Test translation trigger when not ready."""
        mock_orchestrator = MagicMock()
        mock_orchestrator.trigger_translation_manual.return_value = False

        preprocessor = TextPreprocessor(orchestrator=mock_orchestrator)

        result = preprocessor._handle_translation_trigger()

        assert result is False
        mock_print.assert_called_once_with("번역 가능한 컨텐츠가 없습니다.")

    def test_handle_translation_trigger_without_orchestrator(self) -> None:
        """Test translation trigger without orchestrator."""
        preprocessor = TextPreprocessor(orchestrator=None)

        result = preprocessor._handle_translation_trigger()

        assert result is False

    # Trace: SPEC-USER-PROMPTED-001, TEST-USER-PROMPTED-001-AC6
    @patch("builtins.input", return_value="Y")
    def test_handle_exit_confirmation_with_ready_content_yes(
        self, mock_input: MagicMock
    ) -> None:
        """Test exit confirmation when content is ready and user confirms."""
        mock_orchestrator = MagicMock()
        mock_orchestrator.is_translation_ready.return_value = (True, 50000)

        preprocessor = TextPreprocessor(orchestrator=mock_orchestrator)

        result = preprocessor._handle_exit_confirmation()

        assert result is True
        mock_input.assert_called_once()
        assert "50000 tokens" in mock_input.call_args[0][0]

    @patch("builtins.input", return_value="N")
    def test_handle_exit_confirmation_with_ready_content_no(
        self, _mock_input: MagicMock
    ) -> None:
        """Test exit confirmation when content is ready and user cancels."""
        mock_orchestrator = MagicMock()
        mock_orchestrator.is_translation_ready.return_value = (True, 50000)

        preprocessor = TextPreprocessor(orchestrator=mock_orchestrator)

        result = preprocessor._handle_exit_confirmation()

        assert result is False

    def test_handle_exit_confirmation_without_ready_content(self) -> None:
        """Test exit confirmation when no content is ready."""
        mock_orchestrator = MagicMock()
        mock_orchestrator.is_translation_ready.return_value = (False, 0)

        preprocessor = TextPreprocessor(orchestrator=mock_orchestrator)

        result = preprocessor._handle_exit_confirmation()

        # Should exit immediately without confirmation
        assert result is True

    def test_handle_exit_confirmation_without_orchestrator(self) -> None:
        """Test exit confirmation without orchestrator."""
        preprocessor = TextPreprocessor(orchestrator=None)

        result = preprocessor._handle_exit_confirmation()

        # Should exit immediately without confirmation
        assert result is True

    # Trace: SPEC-USER-PROMPTED-001, TEST-USER-PROMPTED-001-AC2
    # Trace: SPEC-USER-PROMPTED-001, TEST-USER-PROMPTED-001-AC3
    @patch("builtins.input")
    @patch("clipboard.paste", return_value="Test content")
    @patch.object(TextPreprocessor, "add_text_to_file")
    def test_run_with_translation_trigger(
        self,
        _mock_add_file: MagicMock,
        _mock_clipboard: MagicMock,
        mock_input: MagicMock,
    ) -> None:
        """Test run loop with translation trigger."""
        mock_orchestrator = MagicMock()
        mock_orchestrator.is_translation_ready.return_value = (True, 45000)
        mock_orchestrator.trigger_translation_manual.return_value = True

        preprocessor = TextPreprocessor(orchestrator=mock_orchestrator)
        preprocessor.page_number = 1

        # Simulate: T to trigger, then B to exit, Y to confirm
        mock_input.side_effect = ["T", "B", "Y"]

        with patch("builtins.print"):
            preprocessor.run()

        # Verify trigger was called
        mock_orchestrator.trigger_translation_manual.assert_called_once()

    @patch("builtins.input")
    def test_run_with_exit_confirmation_cancel(self, mock_input: MagicMock) -> None:
        """Test run loop with exit confirmation cancelled."""
        mock_orchestrator = MagicMock()
        mock_orchestrator.is_translation_ready.return_value = (True, 45000)

        preprocessor = TextPreprocessor(orchestrator=mock_orchestrator)
        preprocessor.page_number = 1

        # Simulate: B to exit, N to cancel, B again, Y to confirm
        mock_input.side_effect = ["B", "N", "B", "Y"]

        preprocessor.run()

        # Should have asked for confirmation twice
        expected_call_count = 4  # 2 menu prompts + 2 confirmations
        assert mock_input.call_count == expected_call_count
