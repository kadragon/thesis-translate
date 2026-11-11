"""Long-polling entry point: ``thesis-translate-bot``."""

from __future__ import annotations

import contextlib
import ctypes
import logging
import os
import signal
import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

from src.bot.config import ConfigError, load_config
from src.bot.glossary import Glossary
from src.bot.handler import handle_update
from src.bot.intake import Intake
from src.bot.jobs import JobQueue
from src.bot.runner import ClaudeRunner
from src.bot.telegram_api import TelegramClient
from src.bot.workspace import Isolation
from src.utils.rich_logging import configure_logging

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping
    from collections.abc import Set as AbstractSet

    from src.bot.config import BotConfig
    from src.bot.handler import Acceptor

logger = logging.getLogger(__name__)

POLL_TIMEOUT_SECONDS = 30
JOBS_DIR = Path("/jobs")
# Root-owned ~/.claude template (settings, plugins) built into the image.
HOME_TEMPLATE = Path("/opt/claude-home")
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


def build_isolation(  # noqa: PLR0913 - keyword-only test seams
    workdir: Path,
    *,
    euid: int | None = None,
    jobs_dir: Path = JOBS_DIR,
    home_template: Path = HOME_TEMPLATE,
    pid: int | None = None,
    glossary: Glossary | None = None,
) -> Isolation | None:
    """Per-job isolation when running as root (the container); else ``None``.

    Raises ``FileNotFoundError`` when the image lacks the HOME template: every
    job would otherwise run without the prod plugin (no kr-style step).
    """
    euid = os.geteuid() if euid is None else euid
    if euid != 0:
        pid = os.getpid() if pid is None else pid
        # Same condition as runner._sweep_strays: only PID 1 sweeps strays.
        cleanup = (
            "" if pid == 1 else " 작업이 끝난 뒤 남은 프로세스도 정리하지 않습니다."
        )
        logger.warning(
            "root가 아니어서 작업별 격리 없이 실행합니다. 작업들이 같은 사용자와 "
            "작업 디렉터리를 공유합니다.%s",
            cleanup,
        )
        return None
    if not (home_template / ".claude").is_dir():
        msg = f"HOME template missing: {home_template / '.claude'}"
        raise FileNotFoundError(msg)
    isolation = Isolation(
        app_dir=workdir,
        jobs_dir=jobs_dir,
        outputs_dir=workdir / "outputs",
        home_template=home_template,
        glossary=glossary,
    )
    isolation.reset()
    return isolation


class Client(Protocol):
    def get_updates(self, offset: int | None, timeout: int) -> list[dict[str, Any]]: ...

    def send_message(self, chat_id: int, text: str) -> None: ...


def poll_once(  # noqa: PLR0913 - glossary wiring is optional
    client: Client,
    allowed: AbstractSet[int],
    intake: Acceptor,
    offset: int | None,
    glossary: Glossary | None = None,
    bot_username: str | None = None,
) -> int | None:
    """Fetch one batch, handle each update, and return the next offset."""
    for update in client.get_updates(offset, POLL_TIMEOUT_SECONDS):
        # Advance first: a failing update is logged and skipped, never replayed
        # (a replay would queue the same PDF again).
        offset = update["update_id"] + 1
        try:
            handle_update(update, allowed, client, intake, glossary, bot_username)
        except Exception:
            logger.exception("업데이트 %s 처리 실패", update.get("update_id"))
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
    # Shared glossary the skill reads; bind-mounted from the host in Compose.
    # One instance, so Telegram edits and per-job snapshots share its lock.
    glossary = Glossary(Path.cwd() / "glossary.json")
    try:
        isolation = build_isolation(Path.cwd(), glossary=glossary)
    except FileNotFoundError as exc:
        logger.error("작업 격리를 준비하지 못해 시작하지 않습니다: %s", exc)  # noqa: TRY400
        return 1
    _serve(config, isolation, glossary)  # pragma: no cover - network loop
    return 0  # pragma: no cover


def _raise_keyboard_interrupt(*_: object) -> None:  # pragma: no cover
    raise KeyboardInterrupt


def _bot_username(client: TelegramClient) -> str:  # pragma: no cover - network
    """``getMe`` until it answers: commands for other bots are told apart by it."""
    while True:
        try:
            return client.get_me()
        except Exception as exc:  # any failure is retried
            logger.warning(
                "봇 정보(getMe) 조회 실패, %d초 후 재시도: %s", RETRY_DELAY_SECONDS, exc
            )
            time.sleep(RETRY_DELAY_SECONDS)


def _serve(  # pragma: no cover - network loop
    config: BotConfig, isolation: Isolation | None, glossary: Glossary
) -> None:
    """Wire client, queue, runner, and intake; poll until Ctrl+C."""
    client = TelegramClient(config.token)
    workdir = Path.cwd()
    queue = JobQueue(runner=ClaudeRunner(client, workdir=workdir, isolation=isolation))
    intake = Intake(
        client,
        queue,
        inbox=workdir / "inbox",
        workdir=workdir,
        outputs=isolation.outputs_dir if isolation else None,
    )
    queue.start()
    # As PID 1 the default SIGTERM action is ignored; stop cleanly on docker stop.
    signal.signal(signal.SIGTERM, _raise_keyboard_interrupt)
    logger.info("봇을 시작합니다. 허용 채팅 %d개", len(config.allowed_chat_ids))
    offset: int | None = None
    # SIGTERM may land anywhere, including the retry sleep; stop cleanly either way.
    with contextlib.suppress(KeyboardInterrupt):
        bot_username = _bot_username(client)
        while True:
            try:
                offset = poll_once(
                    client,
                    config.allowed_chat_ids,
                    intake,
                    offset,
                    glossary,
                    bot_username,
                )
            except Exception as exc:
                logger.warning(
                    "업데이트 수신 실패, %d초 후 재시도: %s", RETRY_DELAY_SECONDS, exc
                )
                time.sleep(RETRY_DELAY_SECONDS)
    logger.info("봇을 종료합니다.")


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
