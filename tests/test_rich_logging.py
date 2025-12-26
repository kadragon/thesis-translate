"""Tests for rich logging and progress integration."""
# Trace: SPEC-RICH-UX-001, TASK-20251226-RICH-UX-01

from __future__ import annotations

import logging
from unittest.mock import patch

from rich.logging import RichHandler

from src.core.streaming_translator import StreamingTranslator, TranslationRunResult
from src.utils.rich_logging import configure_logging, get_console


def test_configure_logging_uses_rich_handler():
    configure_logging()

    root_logger = logging.getLogger()
    rich_handlers = [
        handler for handler in root_logger.handlers if isinstance(handler, RichHandler)
    ]

    assert rich_handlers, "Expected RichHandler to be configured on root logger"
    assert rich_handlers[0].console is get_console()


def test_translate_uses_shared_console_and_transient_progress(tmp_path, monkeypatch):
    input_file = tmp_path / "input.txt"
    input_file.write_text("line\n")

    monkeypatch.setattr(
        StreamingTranslator,
        "_translate_sequential",
        lambda *_args, **_kwargs: TranslationRunResult(
            successes=1, failures=0, duration_seconds=0.0
        ),
    )

    monkeypatch.setattr(
        "src.core.streaming_translator.OpenAI",
        lambda *_args, **_kwargs: object(),
    )

    translator = StreamingTranslator(input_file=str(input_file), max_workers=1)
    monkeypatch.setattr(translator.token_counter, "count_tokens", lambda _text: 1)

    with patch("src.core.streaming_translator.Progress") as mock_progress:
        translator.translate()

        assert mock_progress.call_count == 1
        _args, kwargs = mock_progress.call_args
        assert kwargs["console"] is get_console()
        assert kwargs["transient"] is True
