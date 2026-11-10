"""Turn an accepted PDF document into a queued job: download, check, name."""

from __future__ import annotations

import http.client
import logging
import math
import os
import re
import subprocess
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
_PAGES = re.compile(r"^Pages:\s+(\d+)\s*$", re.MULTILINE)
PDFINFO_TIMEOUT_SECONDS = 10
# pdfinfo parses an untrusted upload: as root, drop to nobody first.
NOBODY = 65534
# Minutes per page, low and high. Calibrated on one 8-page paper (~2.5 min);
# the high end leaves room for dense or table-heavy papers.
MINUTES_PER_PAGE = (0.3, 1.0)


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


def count_pages(pdf: Path) -> int | None:
    """Page count from ``pdfinfo``, or ``None`` when it cannot be read."""
    # No inherited secrets (golden principle 4); C locale keeps "Pages:" stable.
    env = {"PATH": os.environ.get("PATH", os.defpath), "LC_ALL": "C"}
    drop: dict[str, Any] = (
        {"user": NOBODY, "group": NOBODY, "extra_groups": []}
        if os.geteuid() == 0
        else {}
    )
    try:
        proc = subprocess.run(
            ["pdfinfo", str(pdf)],  # poppler-utils (Dockerfile)
            capture_output=True,
            text=True,
            errors="replace",
            timeout=PDFINFO_TIMEOUT_SECONDS,
            env=env,
            check=False,
            **drop,
        )
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return None
    match = _PAGES.search(proc.stdout or "") if proc.returncode == 0 else None
    return int(match.group(1)) if match else None


def _estimate(pages: int | None) -> str:
    if not pages:
        return ""
    low, high = (max(1, math.ceil(pages * rate)) for rate in MINUTES_PER_PAGE)
    span = f"{low}분" if low == high else f"{low}~{high}분"
    return f" {pages}쪽 분량으로 번역에 약 {span} 걸릴 것으로 보입니다."


def _new_id() -> str:
    return uuid4().hex[:8]


class Intake:
    """Downloads into ``inbox`` and enqueues; never overwrites existing outputs."""

    def __init__(  # noqa: PLR0913 - keyword-only injected collaborators
        self,
        downloader: Downloader,
        queue: JobQueue,
        *,
        inbox: Path,
        workdir: Path,
        new_id: Callable[[], str] = _new_id,
        outputs: Path | None = None,
        count_pages: Callable[[Path], int | None] = count_pages,
    ) -> None:
        self._downloader = downloader
        self._queue = queue
        self._inbox = inbox
        self._workdir = workdir
        self._new_id = new_id
        self._outputs = outputs
        self._count_pages = count_pages

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
        pages = self._count_pages(pdf_path)
        position = self._queue.put(Job(job_id, chat_id, file_name, stem, pdf_path))
        logger.info("작업 %s 접수: %s (%d번째, %s쪽)", job_id, stem, position, pages)
        received = f"{file_name} 파일을 받았습니다.{_estimate(pages)}"
        if position == 1:
            return f"{received} 바로 번역을 시작합니다."
        return (
            f"{received} 앞에 {position - 1}건이 있어 "
            "차례가 되면 번역을 시작하고 알려 드립니다."
        )

    def _free_stem(self, stem: str, job_id: str) -> str:
        taken = (
            stem in self._queue.stems()
            or (self._inbox / f"{stem}.pdf").exists()
            or any(
                (self._workdir / f"{stem}{suffix}").exists()
                for suffix in ("_en.txt", "_ko.txt")
            )
            or (self._outputs is not None and (self._outputs / stem).exists())
        )
        return f"{stem}_{job_id}" if taken else stem
