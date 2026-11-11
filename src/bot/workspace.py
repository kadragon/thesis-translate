"""Per-job isolation: a fresh UID and a throwaway directory for every job.

The bot runs as root in the container. Each job gets ``/jobs/<id>/{work,home,tmp}``
owned by a never-reused UID, so code a hostile PDF runs cannot touch the checkout,
earlier outputs, or the next job (docs/design/per-job-isolation.md).
"""

from __future__ import annotations

import contextlib
import logging
import os
import re
import shutil
import stat
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from src.bot.runner import kill_same_uid_strays

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable

    from src.bot.glossary import Glossary
    from src.bot.jobs import Job

logger = logging.getLogger(__name__)

FIRST_JOB_UID = 20000
GLOSSARY = "glossary.json"
# Read-only views of the checkout the skill and CLI need from the job's CWD.
LINKED_ENTRIES = (
    ".claude",
    "src",
    "pyproject.toml",
    "uv.lock",
    ".venv",
    GLOSSARY,
    "AGENTS.md",
    "CLAUDE.md",
    "CLAUDE.local.md",
    ".python-version",
)
OUTPUT_SUFFIXES = ("_en.txt", "_ko.txt", "_terms.json", "_review.md")
MAX_OUTPUT_BYTES = 100 * 1024 * 1024
SHARED_TMP_DIRS = (Path("/tmp"), Path("/var/tmp"), Path("/dev/shm"))
_JOB_ID = re.compile(r"^[\w-]+$")
_COPY_CHUNK = 1024 * 1024
_SWEEP_ROUNDS = 5
_SWEEP_WAIT_SECONDS = 0.05
# UIDs at or above first_uid and below this offset belong to jobs.
_JOB_UID_SPAN = 1_000_000


@dataclass(frozen=True)
class JobSpace:
    uid: int
    root: Path

    @property
    def work(self) -> Path:
        return self.root / "work"

    @property
    def home(self) -> Path:
        return self.root / "home"

    @property
    def tmp(self) -> Path:
        return self.root / "tmp"


class Isolation:
    """Prepares, collects, and discards per-job workspaces (root only)."""

    def __init__(  # noqa: PLR0913 - keyword-only paths and test seams
        self,
        *,
        app_dir: Path,
        jobs_dir: Path,
        outputs_dir: Path,
        home_template: Path,
        first_uid: int = FIRST_JOB_UID,
        chown: Callable[..., None] = os.chown,
        kill_strays: Callable[[int], int] | None = None,
        shared_tmp: Iterable[Path] = SHARED_TMP_DIRS,
        glossary: Glossary | None = None,
    ) -> None:
        self.app_dir = app_dir
        self.jobs_dir = jobs_dir
        self.outputs_dir = outputs_dir
        self.home_template = home_template
        self._next_uid = first_uid
        self._chown = chown
        self._kill_strays = kill_strays or _kill_uid
        self._shared_tmp = tuple(shared_tmp)
        # Set: each job gets a snapshot taken under the glossary's lock instead of
        # a link, so a Telegram edit mid-job cannot hand verify a partial file.
        self.glossary = glossary

    def reset(self) -> None:
        """Delete leftover job dirs: a restart reuses UIDs from the first one."""
        self.jobs_dir.mkdir(parents=True, exist_ok=True)
        for entry in self.jobs_dir.iterdir():
            _remove(entry)
        first = self._next_uid
        for directory in self._shared_tmp:
            _remove_owned(directory, lambda uid: first <= uid < first + _JOB_UID_SPAN)

    def prepare(self, job: Job) -> JobSpace:
        if not _JOB_ID.match(job.job_id):
            msg = f"invalid job id: {job.job_id!r}"
            raise ValueError(msg)
        space = JobSpace(uid=self._next_uid, root=self.jobs_dir / job.job_id)
        self._next_uid += 1
        # The root stays root-owned (0755) so the job cannot swap work/home/tmp.
        space.root.mkdir(parents=True, mode=0o755)
        try:
            self._populate(space, job)
        except BaseException:
            _remove(space.root)
            raise
        return space

    def _populate(self, space: JobSpace, job: Job) -> None:
        for directory in (space.work, space.home, space.tmp):
            directory.mkdir(mode=0o700)
        for name in LINKED_ENTRIES:
            if name == GLOSSARY and self.glossary is not None:
                # Root-owned 0644 copy: readable, not writable, like the link.
                self.glossary.copy_to(space.work / name)
                continue
            target = self.app_dir / name
            if target.exists():
                (space.work / name).symlink_to(target)
        pdf = space.work / f"{job.stem}.pdf"
        shutil.copyfile(job.pdf_path, pdf)
        template = self.home_template / ".claude"
        if template.is_dir():
            shutil.copytree(template, space.home / ".claude", symlinks=True)
        self._own(space, pdf)
        for directory in (space.work, space.home, space.tmp):
            self._own(space, directory)
        for dirpath, dirnames, filenames in os.walk(space.home / ".claude"):
            self._own(space, Path(dirpath))
            for name in [*dirnames, *filenames]:
                self._own(space, Path(dirpath) / name)

    def child_env(self, space: JobSpace) -> dict[str, str]:
        """Per-job overrides for the child environment."""
        return {
            "HOME": str(space.home),
            "USER": f"job{space.uid}",
            "TMPDIR": str(space.tmp),
            "XDG_CACHE_HOME": str(space.tmp / "cache"),
            "XDG_CONFIG_HOME": str(space.home / ".config"),
            "UV_CACHE_DIR": str(space.tmp / "uv-cache"),
        }

    def sweep(self, space: JobSpace) -> bool:
        """Kill every process of the job UID (setsid'd leftovers included).

        Returns ``False`` (and logs) when processes still remain after the last
        round; SIGKILL is asynchronous, so each round waits briefly.
        """
        for _ in range(_SWEEP_ROUNDS):
            if not self._kill_strays(space.uid):
                return True
            time.sleep(_SWEEP_WAIT_SECONDS)
        logger.error("작업 UID %d의 프로세스가 아직 남아 있습니다.", space.uid)
        return False

    def collect(self, space: JobSpace, stem: str) -> Path:
        """Copy regular output files into root-owned ``outputs/<stem>/``.

        Call only after :meth:`sweep`. The workdir is opened without following
        symlinks and each file with ``O_NOFOLLOW``, so a job cannot point the copy
        at files it could not read itself.
        """
        dest = self.outputs_dir / stem
        dest_fd = _open_own_dir(dest)
        try:
            try:
                work_fd = os.open(
                    space.work, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
                )
            except OSError as exc:
                logger.warning(
                    "작업 디렉터리를 열 수 없어 산출물을 복사하지 않습니다: %s", exc
                )
                return dest
            try:
                for suffix in OUTPUT_SUFFIXES:
                    _copy_regular(work_fd, f"{stem}{suffix}", dest_fd)
            finally:
                os.close(work_fd)
        finally:
            os.close(dest_fd)
        return dest

    def discard(self, space: JobSpace) -> None:
        """Sweep the UID, remove its files in shared tmp dirs, delete the job root."""
        self.sweep(space)
        for directory in self._shared_tmp:
            _remove_owned(directory, lambda uid: uid == space.uid)
        _remove(space.root)

    def _own(self, space: JobSpace, path: Path) -> None:
        self._chown(path, space.uid, space.uid, follow_symlinks=False)


def _kill_uid(uid: int) -> int:
    return kill_same_uid_strays(uid=uid)


def _open_own_dir(path: Path) -> int:
    """Create ``path`` if needed and open it, refusing symlinks and foreign owners."""
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o755)
    with contextlib.suppress(FileExistsError):
        path.mkdir(mode=0o755)
    try:
        fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    except OSError as exc:
        msg = f"outputs dir {path} is not a plain directory: {exc}"
        raise OSError(exc.errno, msg) from exc
    if os.fstat(fd).st_uid != os.geteuid():
        os.close(fd)
        msg = f"outputs dir {path} is not owned by the bot"
        raise OSError(msg)
    return fd


def _copy_regular(work_fd: int, name: str, dest_fd: int) -> None:
    try:
        src_fd = os.open(
            name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=work_fd
        )
    except FileNotFoundError:
        return
    except OSError as exc:
        logger.warning("산출물 %s을(를) 건너뜁니다: %s", name, exc)
        return
    with os.fdopen(src_fd, "rb") as src:
        info = os.fstat(src.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size > MAX_OUTPUT_BYTES:
            logger.warning(
                "산출물 %s이(가) 일반 파일이 아니거나 너무 커서 건너뜁니다.", name
            )
            return
        try:
            out_fd = os.open(
                name,
                os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW,
                0o644,
                dir_fd=dest_fd,
            )
        except OSError as exc:
            logger.warning("산출물 %s을(를) outputs에 쓸 수 없습니다: %s", name, exc)
            return
        with os.fdopen(out_fd, "wb") as out:
            os.fchmod(out.fileno(), 0o644)
            shutil.copyfileobj(src, out, _COPY_CHUNK)


def _remove(path: Path) -> None:
    if path.is_symlink() or not path.is_dir():
        path.unlink(missing_ok=True)
    else:
        shutil.rmtree(path)


def _remove_owned(directory: Path, owned: Callable[[int], bool]) -> None:
    """Delete entries whose owner UID matches ``owned`` anywhere under ``directory``."""
    try:
        entries = list(os.scandir(directory))
    except OSError:
        return
    for entry in entries:
        with contextlib.suppress(OSError):
            path = Path(entry.path)
            if owned(entry.stat(follow_symlinks=False).st_uid):
                _remove(path)
            elif entry.is_dir(follow_symlinks=False):
                _remove_owned(path, owned)
