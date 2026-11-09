"""Tests for the headless ``claude -p`` job runner."""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from src.bot.jobs import Job
from src.bot.runner import (
    ALLOWED_TOOLS,
    JOB_TIMEOUT_SECONDS,
    ClaudeRunner,
    build_claude_argv,
    build_prompt,
    kill_same_uid_strays,
    run_in_group,
)
from src.bot.workspace import Isolation

OWNER = 111
JOB = Job("j1", OWNER, "Lacy 2022.pdf", "Lacy 2022", Path("inbox/Lacy 2022.pdf"))


class FakeNotifier:
    def __init__(self):
        self.messages: list[tuple[int, str]] = []
        self.documents: list[tuple[int, Path, str]] = []

    def send_message(self, chat_id, text):
        self.messages.append((chat_id, text))

    def send_document(self, chat_id, path, caption):
        self.documents.append((chat_id, path, caption))


class FakeRun:
    """Records subprocess calls; answers each with the next scripted result."""

    def __init__(self, *results):
        self.results = list(results)
        self.calls: list[tuple[list[str], dict]] = []

    def __call__(self, argv, **kwargs):
        self.calls.append((argv, kwargs))
        result = self.results.pop(0)
        if isinstance(result, BaseException):
            raise result
        return result


def _claude_ok(text="보고: 완료", **extra):
    payload = {"type": "result", "is_error": False, "result": text, **extra}
    return subprocess.CompletedProcess([], 0, stdout=json.dumps(payload), stderr="")


def _runner(tmp_path, run, env=None):
    notifier = FakeNotifier()
    runner = ClaudeRunner(notifier, workdir=tmp_path, run=run, env=env or {})
    return runner, notifier


# --- argv: golden principle 3 ---------------------------------------------


def test_argv_is_headless_with_dont_ask_and_json_output():
    argv = build_claude_argv()

    assert argv[:2] == ["claude", "-p"]
    assert argv[argv.index("--permission-mode") + 1] == "dontAsk"
    assert argv[argv.index("--output-format") + 1] == "json"


def test_argv_ignores_project_mcp_servers():
    # A job could drop a .mcp.json into the shared workdir for the next job.
    assert "--strict-mcp-config" in build_claude_argv()


def test_argv_never_bypasses_permissions():
    joined = " ".join(build_claude_argv())

    assert "--dangerously-skip-permissions" not in joined
    assert "bypassPermissions" not in joined


def test_argv_allows_exactly_the_tool_allowlist():
    argv = build_claude_argv()
    start = argv.index("--allowedTools") + 1
    end = argv.index("--disallowedTools")

    assert tuple(argv[start:end]) == ALLOWED_TOOLS


def test_allowlist_has_no_web_tools_and_denies_them_explicitly():
    argv = build_claude_argv()
    denied = argv[argv.index("--disallowedTools") + 1 :]

    assert not any(tool.startswith(("WebFetch", "WebSearch")) for tool in ALLOWED_TOOLS)
    assert {"WebFetch", "WebSearch"} <= set(denied)


@pytest.mark.parametrize(
    "rule",
    [
        "Edit(./src/**)",
        "Write(./src/**)",
        "Edit(./.claude/**)",
        "Write(./.claude/**)",
        "Edit(./glossary.json)",
        "Write(./.venv/**)",
        "Write(./.mcp.json)",
        "Write(./pyproject.toml)",
        "Read(./.env)",
    ],
)
def test_repo_code_config_and_secrets_are_denied(rule):
    argv = build_claude_argv()

    assert rule in argv[argv.index("--disallowedTools") + 1 :]


def test_allowlist_python_entries_are_the_only_arbitrary_code_paths():
    # The skill's UTF-8 bulk edits and kr-style audit need Python; the container
    # is the sandbox for that (docs/architecture.md). Nothing else runs freely.
    bash = {tool for tool in ALLOWED_TOOLS if tool.startswith("Bash(")}

    assert bash == {
        "Bash(uv run thesis-translate:*)",
        "Bash(pdftotext:*)",
        "Bash(head:*)",
        "Bash(uv run python:*)",
        "Bash(python3:*)",
    }


def test_prompt_names_skill_pdf_and_stem_and_forbids_glossary_edits():
    prompt = build_prompt(JOB)

    assert "translate-paper" in prompt
    assert "inbox/Lacy 2022.pdf" in prompt
    assert "Lacy 2022_ko.txt" in prompt
    assert "glossary.json" in prompt


# --- running ---------------------------------------------------------------


def test_runner_announces_start_and_runs_claude_from_workdir(tmp_path):
    run = FakeRun(_claude_ok())
    runner, notifier = _runner(tmp_path, run)

    runner(JOB)

    argv, kwargs = run.calls[0]
    assert argv == build_claude_argv()
    assert kwargs["cwd"] == tmp_path
    assert kwargs["input"] == build_prompt(JOB)
    assert kwargs["timeout"] == JOB_TIMEOUT_SECONDS
    assert "번역을 시작합니다" in notifier.messages[0][1]


def test_child_env_is_an_allowlist_without_bot_or_other_secrets(tmp_path):
    run = FakeRun(_claude_ok())
    env = {
        "TELEGRAM_BOT_TOKEN": "secret",
        "TELEGRAM_ALLOWED_CHAT_IDS": "111",
        "AWS_SECRET_ACCESS_KEY": "aws",
        "CLAUDE_CODE_OAUTH_TOKEN": "oauth",
        "PATH": "/usr/bin",
        "HOME": "/home/bot",
        "UV_NO_SYNC": "1",
        "UV_NO_CONFIG": "1",
    }
    runner, _ = _runner(tmp_path, run, env)

    runner(JOB)

    assert run.calls[0][1]["env"] == {
        "CLAUDE_CODE_OAUTH_TOKEN": "oauth",
        "PATH": "/usr/bin",
        "HOME": "/home/bot",
        "UV_NO_SYNC": "1",
        "UV_NO_CONFIG": "1",
    }


def test_claude_error_result_is_reported(tmp_path):
    payload = {"type": "result", "is_error": True, "result": "스캔본입니다."}
    run = FakeRun(subprocess.CompletedProcess([], 1, stdout=json.dumps(payload)))
    runner, notifier = _runner(tmp_path, run)

    runner(JOB)

    last = notifier.messages[-1][1]
    assert "번역하지 못했습니다" in last
    assert "스캔본입니다." in last
    assert notifier.documents == []


def test_claude_crash_without_json_reports_stderr_tail(tmp_path):
    run = FakeRun(subprocess.CompletedProcess([], 2, stdout="", stderr="auth failed\n"))
    runner, notifier = _runner(tmp_path, run)

    runner(JOB)

    assert "auth failed" in notifier.messages[-1][1]


def test_timeout_is_reported(tmp_path):
    run = FakeRun(subprocess.TimeoutExpired(["claude"], JOB_TIMEOUT_SECONDS))
    runner, notifier = _runner(tmp_path, run)

    runner(JOB)

    assert "시간" in notifier.messages[-1][1]


def test_missing_claude_binary_is_reported(tmp_path):
    run = FakeRun(FileNotFoundError("claude"))
    runner, notifier = _runner(tmp_path, run)

    runner(JOB)

    assert "claude" in notifier.messages[-1][1]


def test_long_failure_text_is_truncated_to_telegram_limit(tmp_path):
    payload = {"type": "result", "is_error": True, "result": "가" * 10_000}
    run = FakeRun(subprocess.CompletedProcess([], 1, stdout=json.dumps(payload)))
    runner, notifier = _runner(tmp_path, run)

    runner(JOB)

    assert len(notifier.messages[-1][1]) <= 4096  # noqa: PLR2004 - Telegram limit


# --- result gate: golden principle 5 ----------------------------------------


def _verify(code, output=""):
    return subprocess.CompletedProcess([], code, stdout=output, stderr="")


def _write_outputs(tmp_path, stem="Lacy 2022"):
    (tmp_path / f"{stem}_en.txt").write_text("  p.1\n\n  Body.\n", encoding="utf-8")
    ko = tmp_path / f"{stem}_ko.txt"
    ko.write_text("  p.1\n\n  본문.\n", encoding="utf-8")
    return ko


def test_verified_translation_is_sent_as_document_then_report(tmp_path):
    ko = _write_outputs(tmp_path)
    run = FakeRun(_claude_ok("보고: 10쪽"), _verify(0))
    runner, notifier = _runner(tmp_path, run)

    runner(JOB)

    argv, kwargs = run.calls[1]
    assert argv[-3:] == ["verify", "Lacy 2022_en.txt", "Lacy 2022_ko.txt"]
    # -P: a model-written json.py in the workdir must not shadow the stdlib.
    assert argv[1:4] == ["-P", "-m", "src.main"]
    assert kwargs["cwd"] == tmp_path
    assert notifier.documents == [(OWNER, ko, "Lacy 2022.pdf 번역본")]
    assert notifier.messages[-1] == (OWNER, "보고: 10쪽")


def test_failed_verify_sends_no_document(tmp_path):
    _write_outputs(tmp_path)
    run = FakeRun(_claude_ok(), _verify(1, "p.3: 문단 수 4 != 5\n"))
    runner, notifier = _runner(tmp_path, run)

    runner(JOB)

    assert notifier.documents == []
    last = notifier.messages[-1][1]
    assert "검증" in last
    assert "p.3: 문단 수 4 != 5" in last


def test_missing_translation_file_is_reported_with_claude_report(tmp_path):
    run = FakeRun(_claude_ok("스캔본이라 중단했습니다."))
    runner, notifier = _runner(tmp_path, run)

    runner(JOB)

    assert len(run.calls) == 1
    assert notifier.documents == []
    assert "스캔본이라 중단했습니다." in notifier.messages[-1][1]


def test_oversized_translation_is_not_uploaded(tmp_path, monkeypatch):
    _write_outputs(tmp_path)
    monkeypatch.setattr("src.bot.runner.MAX_UPLOAD_BYTES", 1)
    run = FakeRun(_claude_ok(), _verify(0))
    runner, notifier = _runner(tmp_path, run)

    runner(JOB)

    assert notifier.documents == []
    assert "50 MB" in notifier.messages[-1][1]


def test_verify_that_cannot_run_is_reported(tmp_path):
    _write_outputs(tmp_path)
    run = FakeRun(_claude_ok(), subprocess.TimeoutExpired(["verify"], 300))
    runner, notifier = _runner(tmp_path, run)

    runner(JOB)

    assert notifier.documents == []
    assert "verify" in notifier.messages[-1][1]


# --- review fixes (PR #99) --------------------------------------------------


def test_report_and_failure_text_never_carry_secrets(tmp_path):
    _write_outputs(tmp_path)
    leaked = "보고 oauth-secret-123 sk-ant-oat01-AbC_d-9 끝"
    run = FakeRun(_claude_ok(leaked), _verify(0))
    env = {
        "CLAUDE_CODE_OAUTH_TOKEN": "oauth-secret-123",
        "TELEGRAM_BOT_TOKEN": "tg-tok",
    }
    runner, notifier = _runner(tmp_path, run, env)

    runner(JOB)

    text = notifier.messages[-1][1]
    assert "oauth-secret-123" not in text
    assert "sk-ant-oat01" not in text
    assert "보고" in text


def test_failure_stderr_is_redacted(tmp_path):
    run = FakeRun(subprocess.CompletedProcess([], 1, stdout="", stderr="tg-tok leaked"))
    runner, notifier = _runner(tmp_path, run, {"TELEGRAM_BOT_TOKEN": "tg-tok"})

    runner(JOB)

    assert "tg-tok" not in notifier.messages[-1][1]


BLIP = "network blip"
TOO_LARGE_UPLOAD = "Telegram sendDocument 실패: Request Entity Too Large"


class FlakyNotifier(FakeNotifier):
    def __init__(self, fail_first_message=False, fail_document=False):
        super().__init__()
        self.fail_first_message = fail_first_message
        self.fail_document = fail_document

    def send_message(self, chat_id, text):
        if self.fail_first_message:
            self.fail_first_message = False
            raise OSError(BLIP)
        super().send_message(chat_id, text)

    def send_document(self, chat_id, path, caption):
        if self.fail_document:
            raise RuntimeError(TOO_LARGE_UPLOAD)
        super().send_document(chat_id, path, caption)


def test_failed_start_message_does_not_drop_the_job(tmp_path):
    _write_outputs(tmp_path)
    run = FakeRun(_claude_ok(), _verify(0))
    notifier = FlakyNotifier(fail_first_message=True)
    runner = ClaudeRunner(notifier, workdir=tmp_path, run=run, env={})

    runner(JOB)

    assert [argv[0] for argv, _ in run.calls] == ["claude", sys.executable]
    assert len(notifier.documents) == 1


def test_failed_upload_tells_the_user_where_the_file_is(tmp_path):
    _write_outputs(tmp_path)
    run = FakeRun(_claude_ok(), _verify(0))
    notifier = FlakyNotifier(fail_document=True)
    runner = ClaudeRunner(notifier, workdir=tmp_path, run=run, env={})

    runner(JOB)

    last = notifier.messages[-1][1]
    assert "보내지 못했습니다" in last
    assert "Lacy 2022_ko.txt" in last


@pytest.mark.parametrize(
    "rule",
    [
        "Write(./.agents/**)",
        "Write(./CLAUDE.local.md)",
        "Edit(./README.md)",
        "Write(./Dockerfile)",
        "Edit(./backlog.md)",
        "Write(./.python-version)",
    ],
)
def test_files_that_steer_later_runs_are_denied(rule):
    argv = build_claude_argv()

    assert rule in argv[argv.index("--disallowedTools") + 1 :]


def test_run_in_group_kills_grandchildren_on_timeout(tmp_path):
    pid_file = tmp_path / "pid"
    script = f"sleep 30 & echo $! > '{pid_file}'; wait"

    with pytest.raises(subprocess.TimeoutExpired):
        run_in_group(["sh", "-c", script], input="", timeout=1)

    grandchild = int(pid_file.read_text())
    for _ in range(50):
        try:
            os.kill(grandchild, 0)
        except ProcessLookupError:
            break
        time.sleep(0.05)
    else:
        pytest.fail("grandchild still alive")


def test_run_in_group_returns_output_and_code():
    proc = run_in_group(["sh", "-c", "cat; exit 3"], input="hi", timeout=5)

    assert (proc.returncode, proc.stdout) == (3, "hi")


def _fake_proc(tmp_path, entries):
    for pid, uid in entries:
        d = tmp_path / str(pid)
        d.mkdir()
        (d / "status").write_text(f"Name:\tx\nUid:\t{uid}\t{uid}\t{uid}\t{uid}\n")
    (tmp_path / "self").mkdir()
    return tmp_path


def test_kill_same_uid_strays_spares_self_and_other_users(tmp_path):
    proc = _fake_proc(tmp_path, [(1, 10001), (40, 10001), (41, 0), (42, 10001)])
    killed: list[int] = []

    count = kill_same_uid_strays(
        proc_root=proc, self_pid=1, uid=10001, kill=lambda pid, _sig: killed.append(pid)
    )

    assert sorted(killed) == [40, 42]
    assert count == len(killed)


def test_kill_same_uid_strays_ignores_processes_that_already_exited(tmp_path):
    proc = _fake_proc(tmp_path, [(40, 10001)])

    def gone(_pid, _sig):
        raise ProcessLookupError

    assert kill_same_uid_strays(proc_root=proc, self_pid=1, uid=10001, kill=gone) == 0


def test_runner_sweeps_strays_only_as_pid_1(tmp_path, monkeypatch):
    swept: list[bool] = []
    monkeypatch.setattr(
        "src.bot.runner.kill_same_uid_strays", lambda: swept.append(True)
    )
    run = FakeRun(_claude_ok())

    monkeypatch.setattr("src.bot.runner.os.getpid", lambda: 4321)
    _runner(tmp_path, run)[0](JOB)
    assert swept == []

    run = FakeRun(_claude_ok())
    monkeypatch.setattr("src.bot.runner.os.getpid", lambda: 1)
    _runner(tmp_path, run)[0](JOB)
    assert swept == [True]


# --- per-job isolation (root mode) -------------------------------------------


class FakeIsolation:
    """Real directory layout under tmp_path; records sweeps and discards."""

    def __init__(self, tmp_path):
        app = tmp_path / "app"
        (app / "inbox").mkdir(parents=True, exist_ok=True)
        self.swept: list[int] = []
        self.inner = Isolation(
            app_dir=app,
            jobs_dir=tmp_path / "jobs",
            outputs_dir=app / "outputs",
            home_template=tmp_path / "no-template",
            chown=lambda *_a, **_k: None,
            kill_strays=lambda uid: self.swept.append(uid) or 0,
            shared_tmp=(),
        )
        self.spaces: list = []

    def prepare(self, job):
        space = self.inner.prepare(job)
        self.spaces.append(space)
        return space

    def __getattr__(self, name):
        return getattr(self.inner, name)


def _iso_job(tmp_path):
    pdf = tmp_path / "app" / "inbox" / "Lacy 2022.pdf"
    pdf.parent.mkdir(parents=True, exist_ok=True)
    pdf.write_bytes(b"%PDF-1.7\n")
    return Job("j1", OWNER, "Lacy 2022.pdf", "Lacy 2022", pdf)


class WritingRun(FakeRun):
    """Like FakeRun, but the claude call leaves outputs in its cwd."""

    def __call__(self, argv, **kwargs):
        if argv[0] == "claude":
            _write_outputs(kwargs["cwd"])
        return super().__call__(argv, **kwargs)


def _iso_runner(tmp_path, run):
    iso = FakeIsolation(tmp_path)
    notifier = FakeNotifier()
    env = {"PATH": "/usr/bin", "HOME": "/root", "CLAUDE_CONFIG_DIR": "/root/.claude"}
    runner = ClaudeRunner(notifier, workdir=tmp_path, run=run, env=env, isolation=iso)
    return runner, notifier, iso


def test_isolated_job_runs_as_job_uid_in_its_workspace(tmp_path):
    run = WritingRun(_claude_ok(), _verify(0))
    runner, _, iso = _iso_runner(tmp_path, run)
    job = _iso_job(tmp_path)

    runner(job)

    space = iso.spaces[0]
    argv, kwargs = run.calls[0]
    assert argv == build_claude_argv()
    assert kwargs["cwd"] == space.work
    assert (kwargs["user"], kwargs["group"], kwargs["extra_groups"]) == (
        space.uid,
        space.uid,
        [],
    )
    assert kwargs["env"]["HOME"] == str(space.home)
    assert kwargs["env"]["TMPDIR"] == str(space.tmp)
    assert kwargs["env"]["PATH"] == "/usr/bin"
    assert "CLAUDE_CONFIG_DIR" not in kwargs["env"]
    # The prompt names the PDF copy inside the job workdir, not the inbox.
    assert "`Lacy 2022.pdf`" in kwargs["input"]
    assert "inbox" not in kwargs["input"]


def test_isolated_job_verifies_and_sends_the_copied_output(tmp_path):
    run = WritingRun(_claude_ok("보고"), _verify(0))
    runner, notifier, iso = _iso_runner(tmp_path, run)

    runner(_iso_job(tmp_path))

    space = iso.spaces[0]
    out = tmp_path / "app" / "outputs" / "Lacy 2022"
    argv, kwargs = run.calls[1]
    assert argv[-3:] == ["verify", "Lacy 2022_en.txt", "Lacy 2022_ko.txt"]
    assert kwargs["cwd"] == out
    assert (kwargs["user"], kwargs["group"], kwargs["extra_groups"]) == (
        space.uid,
        space.uid,
        [],
    )
    assert notifier.documents == [
        (OWNER, out / "Lacy 2022_ko.txt", "Lacy 2022.pdf 번역본")
    ]
    assert notifier.messages[-1] == (OWNER, "보고")


def test_isolated_failed_verify_sends_no_document(tmp_path):
    run = WritingRun(_claude_ok(), _verify(1, "p.3: 문단 수 4 != 5\n"))
    runner, notifier, _ = _iso_runner(tmp_path, run)

    runner(_iso_job(tmp_path))

    assert notifier.documents == []
    assert "검증" in notifier.messages[-1][1]


def test_isolated_workspace_is_discarded_after_success(tmp_path):
    run = WritingRun(_claude_ok(), _verify(0))
    runner, _, iso = _iso_runner(tmp_path, run)

    runner(_iso_job(tmp_path))

    space = iso.spaces[0]
    assert not space.root.exists()
    assert space.uid in iso.swept


def test_isolated_workspace_is_discarded_after_failure(tmp_path):
    payload = {"type": "result", "is_error": True, "result": "스캔본입니다."}
    run = FakeRun(subprocess.CompletedProcess([], 1, stdout=json.dumps(payload)))
    runner, notifier, iso = _iso_runner(tmp_path, run)

    runner(_iso_job(tmp_path))

    assert not iso.spaces[0].root.exists()
    assert iso.spaces[0].uid in iso.swept
    assert "스캔본입니다." in notifier.messages[-1][1]


def test_isolated_workspace_is_discarded_after_timeout(tmp_path):
    run = FakeRun(subprocess.TimeoutExpired("claude", JOB_TIMEOUT_SECONDS))
    runner, _, iso = _iso_runner(tmp_path, run)

    runner(_iso_job(tmp_path))

    assert not iso.spaces[0].root.exists()
    assert iso.spaces[0].uid in iso.swept


def test_isolated_job_sweeps_uid_before_collecting_outputs(tmp_path):
    order: list[str] = []
    run = WritingRun(_claude_ok(), _verify(0))
    runner, _, iso = _iso_runner(tmp_path, run)
    iso.inner._kill_strays = lambda _uid: order.append("sweep") or 0
    collect = iso.inner.collect
    iso.inner.collect = lambda *a: order.append("collect") or collect(*a)

    runner(_iso_job(tmp_path))

    assert order[:2] == ["sweep", "collect"]


def test_shared_mode_runs_without_uid_switch(tmp_path):
    run = FakeRun(_claude_ok())
    runner, _ = _runner(tmp_path, run)

    runner(JOB)

    assert "user" not in run.calls[0][1]


def test_failed_copy_out_is_reported_and_workspace_discarded(tmp_path):
    run = WritingRun(_claude_ok())
    runner, notifier, iso = _iso_runner(tmp_path, run)

    def broken(*_a):
        raise OSError(28, "No space left on device")

    iso.inner.collect = broken

    runner(_iso_job(tmp_path))

    assert notifier.documents == []
    assert "No space left" in notifier.messages[-1][1]
    assert not iso.spaces[0].root.exists()


def test_kill_same_uid_strays_skips_zombies(tmp_path):
    proc = _fake_proc(tmp_path, [(40, 10001)])
    status = proc / "40" / "status"
    status.write_text("Name:\tx\nState:\tZ (zombie)\n" + status.read_text())
    killed: list[int] = []

    count = kill_same_uid_strays(
        proc_root=proc, self_pid=1, uid=10001, kill=lambda pid, _s: killed.append(pid)
    )

    assert (count, killed) == (0, [])
