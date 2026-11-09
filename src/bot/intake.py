"""Turn an accepted PDF document into a queued job: download, check, name."""

from __future__ import annotations

import http.client
import logging
import re
from typing import TYPE_CHECKING, Any, Protocol
from uuid import uuid4

from src.bot.jobs import Job

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from src.bot.jobs import JobQueue

logger = logging.getLogger(__name__)

DOWNLOAD_FAILED = "파일을 내려받지 못했습니다. 잠시 후 다시 보내 주세요."
NOT_PDF_CONTENT = "PDF 형식이 아닌 파일입니다. 논문 PDF를 보내 주세요."

# Bytes, not characters: leaves room for `_<job id>_terms.json` under the
# 255-byte filename limit even for 3-byte Korean syllables.
MAX_STEM_BYTES = 150
# PDF readers accept the header anywhere in the first 1024 bytes.
_PDF_HEADER = b"%PDF-"
_HEADER_WINDOW = 1024
_UNSAFE = re.compile(r"[^\w .,()\-]")
_DEFAULT_STEM = "paper"


class Downloader(Protocol):
    def get_file(self, file_id: str) -> str: ...

    def download_file(self, file_path: str, dest: Path) -> None: ...


def sanitize_stem(file_name: str) -> str:
    """File-name stem safe for ``<stem>_en.txt`` and CLI args (no path, no flag)."""
    name = re.split(r"[/\\]", file_name)[-1]
    if name.lower().endswith(".pdf"):
        name = name[: -len(".pdf")]
    stem = _UNSAFE.sub("_", name).lstrip("-. ")
    stem = stem.encode()[:MAX_STEM_BYTES].decode("utf-8", "ignore").rstrip(". ")
    return stem or _DEFAULT_STEM


def _new_id() -> str:
    return uuid4().hex[:8]


class Intake:
    """Downloads into ``inbox`` and enqueues; never overwrites existing outputs."""

    def __init__(
        self,
        downloader: Downloader,
        queue: JobQueue,
        *,
        inbox: Path,
        workdir: Path,
        new_id: Callable[[], str] = _new_id,
    ) -> None:
        self._downloader = downloader
        self._queue = queue
        self._inbox = inbox
        self._workdir = workdir
        self._new_id = new_id

    def accept(self, chat_id: int, document: dict[str, Any]) -> str:
        """Return the reply text for the user."""
        file_name = document.get("file_name") or "논문.pdf"
        job_id = self._new_id()
        stem = self._free_stem(sanitize_stem(file_name), job_id)
        self._inbox.mkdir(parents=True, exist_ok=True)
        pdf_path = self._inbox / f"{stem}.pdf"
        try:
            remote = self._downloader.get_file(document["file_id"])
            self._downloader.download_file(remote, pdf_path)
        except (
            OSError,
            RuntimeError,
            ValueError,
            KeyError,
            http.client.HTTPException,
        ) as exc:
            logger.warning("다운로드 실패(%s): %s", file_name, exc)
            pdf_path.unlink(missing_ok=True)
            return DOWNLOAD_FAILED
        with pdf_path.open("rb") as handle:
            is_pdf = _PDF_HEADER in handle.read(_HEADER_WINDOW)
        if not is_pdf:
            pdf_path.unlink()
            return NOT_PDF_CONTENT
        position = self._queue.put(Job(job_id, chat_id, file_name, stem, pdf_path))
        logger.info("작업 %s 접수: %s (%d번째)", job_id, stem, position)
        if position == 1:
            return f"{file_name} 파일을 받았습니다. 곧 번역을 시작합니다."
        return (
            f"{file_name} 파일을 받았습니다. "
            f"앞에 {position - 1}건이 있어 차례가 되면 번역을 시작합니다."
        )

    def _free_stem(self, stem: str, job_id: str) -> str:
        taken = (
            stem in self._queue.stems()
            or (self._inbox / f"{stem}.pdf").exists()
            or any(
                (self._workdir / f"{stem}{suffix}").exists()
                for suffix in ("_en.txt", "_ko.txt")
            )
        )
        return f"{stem}_{job_id}" if taken else stem
