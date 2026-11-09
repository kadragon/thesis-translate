"""Single-worker translation queue."""

from __future__ import annotations

import logging
import threading
from collections import deque
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Job:
    job_id: str
    chat_id: int
    file_name: str
    stem: str
    pdf_path: Path


class JobQueue:
    """FIFO of jobs run one at a time — jobs share the repo root as CWD."""

    def __init__(self, runner: Callable[[Job], None]) -> None:
        self._runner = runner
        self._jobs: deque[Job] = deque()
        self._running: Job | None = None
        self._cond = threading.Condition()

    def put(self, job: Job) -> int:
        """Enqueue and return the 1-based position, counting the running job."""
        with self._cond:
            self._jobs.append(job)
            position = len(self._jobs) + (1 if self._running else 0)
            self._cond.notify()
        return position

    def pending(self) -> list[Job]:
        with self._cond:
            return list(self._jobs)

    def stems(self) -> set[str]:
        """Stems of queued and running jobs (their output names are reserved)."""
        with self._cond:
            stems = {job.stem for job in self._jobs}
            if self._running:
                stems.add(self._running.stem)
        return stems

    def process_one(self) -> None:
        """Block until a job is available, then run it. Runner errors are logged."""
        with self._cond:
            while not self._jobs:
                self._cond.wait()
            job = self._running = self._jobs.popleft()
        try:
            self._runner(job)
        except Exception:
            logger.exception("작업 %s(%s) 실행 중 오류", job.job_id, job.file_name)
        finally:
            with self._cond:
                self._running = None

    def start(self) -> threading.Thread:
        thread = threading.Thread(
            target=self._loop, name="translate-worker", daemon=True
        )
        thread.start()
        return thread

    def _loop(self) -> None:  # pragma: no cover - exercised via start()
        while True:
            self.process_one()
