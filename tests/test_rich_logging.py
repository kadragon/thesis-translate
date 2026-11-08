"""Tests for rich logging and progress integration."""
# Trace: SPEC-RICH-UX-001, TASK-20251226-RICH-UX-01

from __future__ import annotations

import logging

from rich.logging import RichHandler

from src.utils.rich_logging import configure_logging, get_console


def test_configure_logging_uses_rich_handler():
    configure_logging()

    root_logger = logging.getLogger()
    rich_handlers = [
        handler for handler in root_logger.handlers if isinstance(handler, RichHandler)
    ]

    assert rich_handlers, "Expected RichHandler to be configured on root logger"
    assert rich_handlers[0].console is get_console()
