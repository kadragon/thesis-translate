"""Tests for the headless ``claude -p`` job runner."""

import json
import subprocess
from pathlib import Path

from src.bot.jobs import Job
from src.bot.runner import (
    ALLOWED_TOOLS,
    JOB_TIMEOUT_SECONDS,
    ClaudeRunner,
    build_claude_argv,
    build_prompt,
)

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


def test_child_env_drops_telegram_secrets_and_keeps_claude_auth(tmp_path):
    run = FakeRun(_claude_ok())
    env = {
        "TELEGRAM_BOT_TOKEN": "secret",
        "TELEGRAM_ALLOWED_CHAT_IDS": "111",
        "CLAUDE_CODE_OAUTH_TOKEN": "oauth",
        "PATH": "/usr/bin",
    }
    runner, _ = _runner(tmp_path, run, env)

    runner(JOB)

    assert run.calls[0][1]["env"] == {
        "CLAUDE_CODE_OAUTH_TOKEN": "oauth",
        "PATH": "/usr/bin",
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
