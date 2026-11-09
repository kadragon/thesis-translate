"""Tests for per-job isolation: workspace layout, output copy-out, cleanup."""

import dataclasses
import os
from pathlib import Path

import pytest

from src.bot.jobs import Job
from src.bot.workspace import FIRST_JOB_UID, LINKED_ENTRIES, Isolation

OWNER = 111


def _job(tmp_path, job_id="j1", stem="Lacy 2022"):
    inbox = tmp_path / "app" / "inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    pdf = inbox / f"{stem}.pdf"
    pdf.write_bytes(b"%PDF-1.7\n")
    return Job(job_id, OWNER, f"{stem}.pdf", stem, pdf)


class Recorder:
    def __init__(self):
        self.chowns: list[tuple[Path, int, int]] = []
        self.killed: list[int] = []

    def chown(self, path, uid, gid, **_):
        self.chowns.append((Path(path), uid, gid))

    def kill_strays(self, uid):
        self.killed.append(uid)
        return 0


def _isolation(tmp_path, rec=None, shared_tmp=()):
    rec = rec or Recorder()
    app = tmp_path / "app"
    app.mkdir(exist_ok=True)
    for name in ("src", ".claude"):
        (app / name).mkdir(exist_ok=True)
    (app / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
    template = tmp_path / "home-template"
    (template / ".claude" / "plugins").mkdir(parents=True, exist_ok=True)
    (template / ".claude" / "settings.json").write_text("{}", encoding="utf-8")
    iso = Isolation(
        app_dir=app,
        jobs_dir=tmp_path / "jobs",
        outputs_dir=app / "outputs",
        home_template=template,
        chown=rec.chown,
        kill_strays=rec.kill_strays,
        shared_tmp=shared_tmp,
    )
    return iso, rec


def test_prepare_gives_each_job_a_new_uid(tmp_path):
    iso, _ = _isolation(tmp_path)

    first = iso.prepare(_job(tmp_path, "j1"))
    second = iso.prepare(_job(tmp_path, "j2"))

    assert (first.uid, second.uid) == (FIRST_JOB_UID, FIRST_JOB_UID + 1)
    assert first.root == tmp_path / "jobs" / "j1"


def test_prepare_links_app_entries_copies_pdf_and_seeds_home(tmp_path):
    iso, rec = _isolation(tmp_path)

    space = iso.prepare(_job(tmp_path))

    assert (space.work / "src").is_symlink()
    assert (space.work / "src").resolve() == (tmp_path / "app" / "src").resolve()
    assert (space.work / "pyproject.toml").is_symlink()
    # Only entries that exist in the app dir are linked.
    assert not (space.work / "uv.lock").exists()
    assert not (space.work / "uv.lock").is_symlink()
    assert ".venv" in LINKED_ENTRIES
    pdf = space.work / "Lacy 2022.pdf"
    assert pdf.read_bytes() == b"%PDF-1.7\n"
    assert not pdf.is_symlink()
    assert (space.home / ".claude" / "settings.json").read_text() == "{}"
    owned = {path for path, uid, gid in rec.chowns if uid == gid == space.uid}
    assert {space.work, space.home, space.tmp, pdf} <= owned
    assert space.home / ".claude" in owned
    assert space.home / ".claude" / "settings.json" in owned
    # The job root stays ours so the job cannot swap its own subdirectories.
    assert space.root not in owned


def test_child_env_points_home_tmp_and_caches_into_the_job(tmp_path):
    iso, _ = _isolation(tmp_path)
    space = iso.prepare(_job(tmp_path))

    env = iso.child_env(space)

    assert env["HOME"] == str(space.home)
    assert env["TMPDIR"] == str(space.tmp)
    assert env["USER"] == f"job{space.uid}"
    for key in ("XDG_CACHE_HOME", "XDG_CONFIG_HOME", "UV_CACHE_DIR"):
        assert env[key].startswith(str(space.root) + os.sep)


def _outputs(space, stem="Lacy 2022"):
    for suffix in ("_en.txt", "_ko.txt", "_terms.json", "_review.md"):
        (space.work / f"{stem}{suffix}").write_text(suffix, encoding="utf-8")


def test_collect_copies_regular_outputs_into_outputs_stem_dir(tmp_path):
    iso, _ = _isolation(tmp_path)
    space = iso.prepare(_job(tmp_path))
    _outputs(space)
    (space.work / "Lacy 2022_dual.txt").write_text("not collected", encoding="utf-8")

    out = iso.collect(space, "Lacy 2022")

    assert out == tmp_path / "app" / "outputs" / "Lacy 2022"
    assert sorted(p.name for p in out.iterdir()) == [
        "Lacy 2022_en.txt",
        "Lacy 2022_ko.txt",
        "Lacy 2022_review.md",
        "Lacy 2022_terms.json",
    ]
    assert (out / "Lacy 2022_ko.txt").read_text(encoding="utf-8") == "_ko.txt"
    assert not any(p.is_symlink() for p in out.iterdir())


def test_collect_skips_symlinked_outputs(tmp_path):
    iso, _ = _isolation(tmp_path)
    space = iso.prepare(_job(tmp_path))
    secret = tmp_path / "secret"
    secret.write_text("root only", encoding="utf-8")
    (space.work / "Lacy 2022_ko.txt").symlink_to(secret)

    out = iso.collect(space, "Lacy 2022")

    assert not (out / "Lacy 2022_ko.txt").exists()


def test_collect_skips_fifos(tmp_path):
    iso, _ = _isolation(tmp_path)
    space = iso.prepare(_job(tmp_path))
    os.mkfifo(space.work / "Lacy 2022_ko.txt")

    out = iso.collect(space, "Lacy 2022")

    assert not (out / "Lacy 2022_ko.txt").exists()


def test_collect_refuses_a_workdir_swapped_for_a_symlink(tmp_path):
    iso, _ = _isolation(tmp_path)
    space = iso.prepare(_job(tmp_path))
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (elsewhere / "Lacy 2022_ko.txt").write_text("planted", encoding="utf-8")
    space.work.rename(tmp_path / "moved")
    space.work.symlink_to(elsewhere)

    out = iso.collect(space, "Lacy 2022")

    assert list(out.iterdir()) == []


def test_collect_skips_oversized_outputs(tmp_path, monkeypatch):
    monkeypatch.setattr("src.bot.workspace.MAX_OUTPUT_BYTES", 3)
    iso, _ = _isolation(tmp_path)
    space = iso.prepare(_job(tmp_path))
    _outputs(space)

    out = iso.collect(space, "Lacy 2022")

    assert list(out.iterdir()) == []


def test_discard_sweeps_uid_cleans_shared_tmp_and_removes_job_root(tmp_path):
    shared = tmp_path / "shared-tmp"
    (shared / "nested").mkdir(parents=True)
    rec = Recorder()
    iso, _ = _isolation(tmp_path, rec, shared_tmp=(shared,))
    space = iso.prepare(_job(tmp_path))
    # Files the test creates are owned by our uid; pretend that is the job's.
    space = dataclasses.replace(space, uid=os.getuid())
    (shared / "planted").write_text("x", encoding="utf-8")
    (shared / "nested" / "deep").write_text("x", encoding="utf-8")

    iso.discard(space)

    assert rec.killed == [os.getuid()]
    assert not space.root.exists()
    assert list(shared.iterdir()) == []


def test_discard_spares_shared_tmp_files_of_other_uids(tmp_path):
    shared = tmp_path / "shared-tmp"
    shared.mkdir()
    (shared / "keep").write_text("x", encoding="utf-8")
    iso, _ = _isolation(tmp_path, shared_tmp=(shared,))
    space = iso.prepare(_job(tmp_path))

    iso.discard(space)

    assert (shared / "keep").exists()


def test_reset_removes_leftover_job_dirs(tmp_path):
    iso, _ = _isolation(tmp_path)
    leftover = tmp_path / "jobs" / "old" / "work"
    leftover.mkdir(parents=True)

    iso.reset()

    assert list((tmp_path / "jobs").iterdir()) == []


@pytest.mark.parametrize("job_id", ["../escape", "a/b", ""])
def test_prepare_rejects_job_ids_that_are_not_a_single_name(tmp_path, job_id):
    iso, _ = _isolation(tmp_path)

    with pytest.raises(ValueError, match="job id"):
        iso.prepare(_job(tmp_path, job_id))


def test_collect_never_follows_a_planted_symlink_in_outputs(tmp_path):
    iso, _ = _isolation(tmp_path)
    space = iso.prepare(_job(tmp_path))
    _outputs(space)
    victim = tmp_path / "victim"
    victim.write_text("keep", encoding="utf-8")
    dest = tmp_path / "app" / "outputs" / "Lacy 2022"
    dest.mkdir(parents=True)
    (dest / "Lacy 2022_ko.txt").symlink_to(victim)

    iso.collect(space, "Lacy 2022")

    assert victim.read_text(encoding="utf-8") == "keep"


def test_collect_refuses_an_outputs_dir_that_is_a_symlink(tmp_path):
    iso, _ = _isolation(tmp_path)
    space = iso.prepare(_job(tmp_path))
    _outputs(space)
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (tmp_path / "app" / "outputs").mkdir(parents=True)
    (tmp_path / "app" / "outputs" / "Lacy 2022").symlink_to(elsewhere)

    with pytest.raises(OSError, match="outputs"):
        iso.collect(space, "Lacy 2022")
    assert list(elsewhere.iterdir()) == []


def test_prepare_removes_a_partial_workspace_on_failure(tmp_path):
    iso, _ = _isolation(tmp_path)
    job = _job(tmp_path)
    job.pdf_path.unlink()

    with pytest.raises(OSError):
        iso.prepare(job)
    assert not (tmp_path / "jobs" / "j1").exists()


def test_reset_removes_shared_tmp_files_of_any_job_uid(tmp_path):
    shared = tmp_path / "shared-tmp"
    shared.mkdir()
    (shared / "planted").write_text("x", encoding="utf-8")
    rec = Recorder()
    app = tmp_path / "app"
    app.mkdir()
    iso = Isolation(
        app_dir=app,
        jobs_dir=tmp_path / "jobs",
        outputs_dir=app / "outputs",
        home_template=tmp_path / "none",
        # Our own uid stands in for a job uid left over from before a restart.
        first_uid=os.getuid(),
        chown=rec.chown,
        kill_strays=rec.kill_strays,
        shared_tmp=(shared,),
    )

    iso.reset()

    assert list(shared.iterdir()) == []


def test_sweep_waits_between_rounds_and_logs_survivors(tmp_path, caplog):
    rounds: list[int] = []
    iso, _ = _isolation(tmp_path)
    iso._kill_strays = lambda uid: rounds.append(uid) or 1
    space = iso.prepare(_job(tmp_path))

    assert iso.sweep(space) is False
    assert len(rounds) > 1
    assert "남아" in caplog.text
