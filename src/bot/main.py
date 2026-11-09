"""Long-polling entry point: ``thesis-translate-bot``."""

from __future__ import annotations

import ctypes
import logging
import os
import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

from src.bot.config import ConfigError, load_config
from src.bot.handler import handle_update
from src.bot.intake import Intake
from src.bot.jobs import JobQueue
from src.bot.runner import ClaudeRunner
from src.bot.telegram_api import TelegramClient
from src.utils.rich_logging import configure_logging

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping
    from collections.abc import Set as AbstractSet

    from src.bot.config import BotConfig
    from src.bot.handler import Acceptor

logger = logging.getLogger(__name__)

POLL_TIMEOUT_SECONDS = 30
RETRY_DELAY_SECONDS = 5
PR_SET_DUMPABLE = 4


def _libc() -> Any:  # pragma: no cover - real libc, Linux only
    return ctypes.CDLL(None, use_errno=True)


def disable_dumpable(
    platform: str = sys.platform, load_libc: Callable[[], Any] = _libc
) -> bool:
    """Make ``/proc/<pid>/environ`` and memory unreadable to same-UID processes.

    The ``claude`` child runs as the same user and may execute Python, so
    without this it could read ``TELEGRAM_BOT_TOKEN`` from the bot's environ.
    Returns ``False`` where ``prctl`` does not exist (macOS dev runs).
    """
    if not platform.startswith("linux"):
        return False
    if load_libc().prctl(PR_SET_DUMPABLE, 0, 0, 0, 0) != 0:
        msg = f"prctl(PR_SET_DUMPABLE) failed: errno {ctypes.get_errno()}"
        raise OSError(msg)
    return True


class Client(Protocol):
    def get_updates(self, offset: int | None, timeout: int) -> list[dict[str, Any]]: ...

    def send_message(self, chat_id: int, text: str) -> None: ...


def poll_once(
    client: Client,
    allowed: AbstractSet[int],
    intake: Acceptor,
    offset: int | None,
) -> int | None:
    """Fetch one batch, handle each update, and return the next offset."""
    for update in client.get_updates(offset, POLL_TIMEOUT_SECONDS):
        offset = update["update_id"] + 1
        handle_update(update, allowed, client, intake)
    return offset


def main(env: Mapping[str, str] | None = None) -> int:
    """Run the bot until interrupted; exit 1 on bad configuration."""
    configure_logging()
    try:
        config = load_config(os.environ if env is None else env)
    except ConfigError as exc:
        logger.error("%s", exc)  # noqa: TRY400
        return 1
    try:
        disable_dumpable()
    except OSError as exc:
        logger.error("프로세스 보호(prctl) 설정 실패로 시작하지 않습니다: %s", exc)  # noqa: TRY400
        return 1
    _serve(config)  # pragma: no cover - network loop
    return 0  # pragma: no cover


def _serve(config: BotConfig) -> None:  # pragma: no cover - network loop
    """Wire client, queue, runner, and intake; poll until Ctrl+C."""
    client = TelegramClient(config.token)
    workdir = Path.cwd()
    queue = JobQueue(runner=ClaudeRunner(client, workdir=workdir))
    intake = Intake(client, queue, inbox=workdir / "inbox", workdir=workdir)
    queue.start()
    logger.info("봇을 시작합니다. 허용 채팅 %d개", len(config.allowed_chat_ids))
    offset: int | None = None
    while True:
        try:
            offset = poll_once(client, config.allowed_chat_ids, intake, offset)
        except KeyboardInterrupt:
            return
        except (OSError, RuntimeError, ValueError) as exc:
            logger.warning(
                "업데이트 수신 실패, %d초 후 재시도: %s", RETRY_DELAY_SECONDS, exc
            )
            time.sleep(RETRY_DELAY_SECONDS)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
