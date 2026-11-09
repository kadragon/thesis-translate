"""Run one translation job through headless ``claude -p`` (translate-paper skill).

Paper text is untrusted, so Claude runs with an explicit tool allowlist and
``dontAsk`` — anything not listed is denied (AGENTS.md golden principle 3).
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping
    from pathlib import Path

    from src.bot.jobs import Job

logger = logging.getLogger(__name__)

ALLOWED_TOOLS = (
    "Read",
    "Edit",
    "Write",
    "Glob",
    "Grep",
    "Skill",
    "Agent",
    "TodoWrite",
    "Bash(uv run thesis-translate:*)",
    "Bash(pdftotext:*)",
    "Bash(head:*)",
    # Arbitrary code: the skill's UTF-8 bulk edits and the kr-style audit need
    # Python. Acceptable only because the bot runs in a container.
    "Bash(uv run python:*)",
    "Bash(python3:*)",
)
DISALLOWED_TOOLS = ("WebFetch", "WebSearch")
JOB_TIMEOUT_SECONDS = 4 * 60 * 60
# Telegram rejects messages over 4096 characters.
MAX_MESSAGE_CHARS = 4000
_SECRET_ENV_PREFIX = "TELEGRAM_"

START = "{name} 번역을 시작합니다. 논문 길이에 따라 수십 분 이상 걸릴 수 있습니다."
FAILED = "{name}을(를) 번역하지 못했습니다.\n\n{reason}"


class Notifier(Protocol):
    def send_message(self, chat_id: int, text: str) -> None: ...


def build_prompt(job: Job) -> str:
    """Instructions for the unattended run; the prompt goes in on stdin."""
    stem = job.stem
    return f"""\
Translate the paper PDF `{job.pdf_path.as_posix()}` into Korean by following the
translate-paper skill (.claude/skills/translate-paper/SKILL.md) end to end.

This is an unattended run started from the Telegram bot; nobody can answer questions.
- Run `extract` on `{job.pdf_path.as_posix()}` so the files are `{stem}_en.txt`,
  `{stem}_terms.json`, `{stem}_review.md`, and `{stem}_ko.txt` in the current directory.
- Decide --start-page and --first-pdf-page yourself from the PDF.
- Do not edit glossary.json; list suggested additions in your final message instead.
- Skip the optional dual file.
- If the PDF is a scan or cannot be translated, stop and explain why.
- Your final message is the step-8 report, in Korean, at most 15 lines.
"""


def build_claude_argv() -> list[str]:
    return [
        "claude",
        "-p",
        "--output-format",
        "json",
        "--permission-mode",
        "dontAsk",
        "--no-session-persistence",
        "--allowedTools",
        *ALLOWED_TOOLS,
        "--disallowedTools",
        *DISALLOWED_TOOLS,
    ]


def _child_env(env: Mapping[str, str]) -> dict[str, str]:
    """Drop bot secrets; the model never needs the Telegram token."""
    return {k: v for k, v in env.items() if not k.startswith(_SECRET_ENV_PREFIX)}


def _clip(text: str, limit: int = MAX_MESSAGE_CHARS) -> str:
    text = text.strip()
    return text if len(text) <= limit else "…" + text[-(limit - 1) :]


def _parse_result(stdout: str) -> dict[str, Any]:
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


class ClaudeRunner:
    """Callable used as the ``JobQueue`` runner."""

    def __init__(
        self,
        notifier: Notifier,
        *,
        workdir: Path,
        run: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
        env: Mapping[str, str] | None = None,
    ) -> None:
        self._notifier = notifier
        self._workdir = workdir
        self._run = run
        self._env = os.environ if env is None else env

    def __call__(self, job: Job) -> None:
        self._notifier.send_message(job.chat_id, START.format(name=job.file_name))
        report = self._translate(job)
        if report is not None:
            self._deliver(job, report)

    def _fail(self, job: Job, reason: str) -> None:
        logger.warning("작업 %s 실패: %s", job.job_id, reason[:200])
        message = FAILED.format(name=job.file_name, reason=_clip(reason, 3500))
        self._notifier.send_message(job.chat_id, message)

    def _translate(self, job: Job) -> str | None:
        """Run Claude; return its final report, or ``None`` after reporting failure."""
        try:
            proc = self._run(
                build_claude_argv(),
                cwd=self._workdir,
                input=build_prompt(job),
                capture_output=True,
                text=True,
                timeout=JOB_TIMEOUT_SECONDS,
                env=_child_env(self._env),
                check=False,
            )
        except subprocess.TimeoutExpired:
            self._fail(
                job, f"제한 시간 {JOB_TIMEOUT_SECONDS // 3600}시간을 넘겼습니다."
            )
            return None
        except OSError as exc:
            self._fail(job, f"claude CLI를 실행할 수 없습니다: {exc}")
            return None
        result = _parse_result(proc.stdout or "")
        report = str(result.get("result") or "")
        # Denials mean the allowlist blocked a step the skill needed.
        logger.info(
            "작업 %s: claude 종료 코드 %d, 비용 $%s, 거부된 도구 호출 %d건",
            job.job_id,
            proc.returncode,
            result.get("total_cost_usd", "?"),
            len(result.get("permission_denials") or []),
        )
        if proc.returncode != 0 or result.get("is_error") or not result:
            self._fail(job, report or proc.stderr or f"종료 코드 {proc.returncode}")
            return None
        return report

    def _deliver(self, job: Job, report: str) -> None:
        self._notifier.send_message(job.chat_id, _clip(report))
