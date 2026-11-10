"""Tests for PDF intake (download, stem, collisions) and the single-worker queue."""

import http.client
import os
import subprocess
import threading
from pathlib import Path

import pytest

from src.bot.intake import (
    DOWNLOAD_FAILED,
    NOBODY,
    NOT_PDF_CONTENT,
    Intake,
    count_pages,
    sanitize_stem,
)
from src.bot.jobs import Job, JobQueue

OWNER = 111
PDF_BYTES = b"%PDF-1.7\n..."


class FakeDownloader:
    def __init__(self, content=PDF_BYTES, error=None):
        self.content = content
        self.error = error
        self.file_ids: list[str] = []

    def get_file(self, file_id):
        self.file_ids.append(file_id)
        if self.error:
            raise self.error
        return f"documents/{file_id}.pdf"

    def download_file(self, _file_path, dest):
        dest.write_bytes(self.content)


def _job(stem="paper", job_id="j1"):
    return Job(
        job_id=job_id,
        chat_id=OWNER,
        file_name=f"{stem}.pdf",
        stem=stem,
        pdf_path=Path(f"inbox/{stem}.pdf"),
    )


def _intake(  # noqa: PLR0913 - test helper defaults
    tmp_path,
    downloader=None,
    queue=None,
    ids=("j1", "j2", "j3"),
    outputs=None,
    pages=None,
):
    queue = queue or JobQueue(runner=lambda _job: None)
    id_iter = iter(ids)
    intake = Intake(
        downloader or FakeDownloader(),
        queue,
        inbox=tmp_path / "inbox",
        workdir=tmp_path,
        new_id=lambda: next(id_iter),
        outputs=outputs,
        count_pages=lambda _path: pages,
    )
    return intake, queue


def _doc(name="Lacy 2022.pdf"):
    return {"file_id": "F1", "file_name": name, "mime_type": "application/pdf"}


@pytest.mark.parametrize(
    ("file_name", "stem"),
    [
        (
            "Lacy et al. (2022). Habitual practice.pdf",
            "Lacy et al. (2022). Habitual practice",
        ),
        ("../../etc/passwd.pdf", "passwd"),
        ("a/b:c*d?.pdf", "b_c_d_"),
        ("--force.pdf", "force"),
        ("논문 제목.pdf", "논문 제목"),
        (".pdf", "paper"),
        ("", "paper"),
        ("x" * 300 + ".pdf", "x" * 150),
    ],
)
def test_sanitize_stem(file_name, stem):
    assert sanitize_stem(file_name) == stem


def test_accept_downloads_to_inbox_and_enqueues(tmp_path):
    intake, queue = _intake(tmp_path)

    reply = intake.accept(OWNER, _doc())

    pdf = tmp_path / "inbox" / "Lacy 2022.pdf"
    assert pdf.read_bytes() == PDF_BYTES
    assert queue.pending() == [
        Job("j1", OWNER, "Lacy 2022.pdf", "Lacy 2022", pdf),
    ]
    assert "Lacy 2022.pdf" in reply
    assert "바로 번역을 시작합니다" in reply


def test_second_job_reply_says_how_many_are_ahead(tmp_path):
    intake, _ = _intake(tmp_path)
    intake.accept(OWNER, _doc("a.pdf"))

    reply = intake.accept(OWNER, _doc("b.pdf"))

    assert "앞에 1건" in reply
    assert "알려 드립니다" in reply


def test_reply_gives_page_count_and_time_range(tmp_path):
    intake, _ = _intake(tmp_path, pages=8)

    reply = intake.accept(OWNER, _doc())

    assert "8쪽" in reply
    assert "약 3~8분" in reply


def test_reply_omits_estimate_when_page_count_is_unknown(tmp_path):
    intake, _ = _intake(tmp_path, pages=None)

    reply = intake.accept(OWNER, _doc())

    assert "쪽" not in reply
    assert "분" not in reply.replace("분량", "")


def test_first_job_is_not_marked_waited_but_a_queued_one_is():
    queue = JobQueue(runner=lambda _job: None)
    queue.put(_job("a"))
    queue.put(_job("b", "j2"))

    assert [job.waited for job in queue.pending()] == [False, True]


def test_count_pages_reads_pdfinfo(tmp_path, monkeypatch):
    def fake_run(argv, **_kwargs):
        assert argv[0] == "pdfinfo"
        stdout = "Title: x\nPages:          12\n"
        return subprocess.CompletedProcess(argv, 0, stdout, "")

    monkeypatch.setattr(subprocess, "run", fake_run)

    assert count_pages(tmp_path / "a.pdf") == 12  # noqa: PLR2004


@pytest.mark.parametrize("euid", [0, 1000])
def test_count_pages_runs_without_secrets_or_root(tmp_path, monkeypatch, euid):
    # pdfinfo parses an untrusted upload: no bot/Claude tokens, no root.
    seen: dict = {}

    def fake_run(argv, **kwargs):
        seen.update(kwargs)
        return subprocess.CompletedProcess(argv, 0, "Pages: 3\n", "")

    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tg-tok")
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "oauth-tok")
    monkeypatch.setattr(os, "geteuid", lambda: euid)
    monkeypatch.setattr(subprocess, "run", fake_run)

    assert count_pages(tmp_path / "a.pdf") == 3  # noqa: PLR2004
    assert set(seen["env"]) <= {"PATH", "LC_ALL"}
    if euid == 0:
        assert (seen["user"], seen["group"], seen["extra_groups"]) == (
            NOBODY,
            NOBODY,
            [],
        )
    else:
        assert "user" not in seen


@pytest.mark.parametrize(
    "outcome",
    [
        UnicodeDecodeError("utf-8", b"\xff", 0, 1, "bad"),
        subprocess.CompletedProcess([], 1, "", "Syntax Error"),
        subprocess.CompletedProcess([], 0, "Title: x\n", ""),
        subprocess.TimeoutExpired("pdfinfo", 10),
        FileNotFoundError("pdfinfo"),
    ],
)
def test_count_pages_returns_none_when_unknown(tmp_path, monkeypatch, outcome):
    def fake_run(_argv, **_kwargs):
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome

    monkeypatch.setattr(subprocess, "run", fake_run)

    assert count_pages(tmp_path / "a.pdf") is None


def test_non_pdf_content_is_deleted_and_not_queued(tmp_path):
    intake, queue = _intake(tmp_path, FakeDownloader(content=b"PK\x03\x04 zip"))

    reply = intake.accept(OWNER, _doc())

    assert reply == NOT_PDF_CONTENT
    assert queue.pending() == []
    assert list((tmp_path / "inbox").iterdir()) == []


@pytest.mark.parametrize("error", [RuntimeError("file is too big"), OSError("reset")])
def test_download_failure_replies_and_queues_nothing(tmp_path, error):
    intake, queue = _intake(tmp_path, FakeDownloader(error=error))

    assert intake.accept(OWNER, _doc()) == DOWNLOAD_FAILED
    assert queue.pending() == []


def test_existing_outputs_get_job_id_suffix_instead_of_overwrite(tmp_path):
    (tmp_path / "Lacy 2022_en.txt").write_text("hand cleanup", encoding="utf-8")
    intake, queue = _intake(tmp_path)

    intake.accept(OWNER, _doc())

    assert queue.pending()[0].stem == "Lacy 2022_j1"
    assert (tmp_path / "inbox" / "Lacy 2022_j1.pdf").exists()
    assert (tmp_path / "Lacy 2022_en.txt").read_text(encoding="utf-8") == "hand cleanup"


def test_same_name_twice_in_queue_gets_distinct_stems(tmp_path):
    intake, queue = _intake(tmp_path)

    intake.accept(OWNER, _doc())
    intake.accept(OWNER, _doc())

    assert [job.stem for job in queue.pending()] == ["Lacy 2022", "Lacy 2022_j2"]


def test_queue_runs_jobs_in_order():
    ran: list[str] = []
    queue = JobQueue(runner=lambda job: ran.append(job.stem))
    queue.put(_job("a"))
    queue.put(_job("b"))

    queue.process_one()
    queue.process_one()

    assert ran == ["a", "b"]
    assert queue.pending() == []


def test_running_job_counts_toward_position_and_stems():
    seen: dict[str, object] = {}

    def runner(_current):
        seen["position"] = queue.put(_job("late", "j9"))
        seen["stems"] = queue.stems()

    queue = JobQueue(runner=runner)
    assert queue.put(_job("first")) == 1

    queue.process_one()

    assert seen == {"position": 2, "stems": {"first", "late"}}


def test_runner_failure_does_not_stop_the_queue():
    ran: list[str] = []

    def runner(job):
        ran.append(job.stem)
        if job.stem == "bad":
            raise RuntimeError(job.stem)

    queue = JobQueue(runner=runner)
    queue.put(_job("bad"))
    queue.put(_job("good"))

    queue.process_one()
    queue.process_one()

    assert ran == ["bad", "good"]


def test_started_worker_processes_jobs():
    done = threading.Event()
    queue = JobQueue(runner=lambda _job: done.set())
    queue.start()

    queue.put(_job())

    assert done.wait(timeout=2)


def test_default_job_ids_are_short_and_unique(tmp_path):
    queue = JobQueue(runner=lambda _job: None)
    intake = Intake(FakeDownloader(), queue, inbox=tmp_path / "inbox", workdir=tmp_path)

    intake.accept(OWNER, _doc())
    intake.accept(OWNER, _doc())

    ids = [job.job_id for job in queue.pending()]
    assert len(set(ids)) == len(ids)
    assert all(len(job_id) == len("0123abcd") for job_id in ids)


def test_stem_fits_filename_byte_limit_with_suffixes():
    stem = sanitize_stem("가" * 300 + ".pdf")

    assert len(f"{stem}_j1234567_terms.json".encode()) <= 255  # noqa: PLR2004


def test_truncation_never_splits_a_utf8_character():
    stem = sanitize_stem("a" + "가" * 200 + ".pdf")

    stem.encode("utf-8")  # would fail on a broken surrogate
    assert stem.startswith("a가")


def test_incomplete_read_is_a_download_failure(tmp_path):
    error = http.client.IncompleteRead(b"%PDF-", 1000)
    intake, queue = _intake(tmp_path, FakeDownloader(error=error))

    assert intake.accept(OWNER, _doc()) == DOWNLOAD_FAILED
    assert queue.pending() == []


def test_existing_output_dir_gets_job_id_suffix(tmp_path):
    outputs = tmp_path / "outputs"
    (outputs / "Lacy 2022").mkdir(parents=True)
    intake, queue = _intake(tmp_path, outputs=outputs)

    intake.accept(OWNER, _doc())

    assert queue.pending()[0].stem == "Lacy 2022_j1"
