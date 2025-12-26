"""Rich logging and console helpers."""
# Trace: SPEC-RICH-UX-001, TASK-20251226-RICH-UX-01

from __future__ import annotations

import logging

from rich.console import Console
from rich.logging import RichHandler

_CONSOLE = Console()


def get_console() -> Console:
    """Return the shared console instance for rich output."""
    return _CONSOLE


def configure_logging(level: int = logging.INFO) -> None:
    """Configure logging to use RichHandler with the shared console."""
    logging.basicConfig(
        level=level,
        format="%(name)s: %(message)s",
        handlers=[
            RichHandler(
                console=get_console(),
                rich_tracebacks=True,
                markup=True,
                show_path=False,
            )
        ],
        force=True,
    )
