"""Tests for the Telegram bot: allowlist, routing, polling, config, API client."""

import io
import json
from unittest.mock import patch

import pytest

from src.bot.config import BotConfig, ConfigError, load_config, parse_chat_ids
from src.bot.handler import (
    HINT,
    MAX_DOWNLOAD_BYTES,
    NOT_PDF,
    TOO_LARGE,
    handle_update,
)
from src.bot.main import (
    POLL_TIMEOUT_SECONDS,
    PR_SET_DUMPABLE,
    build_isolation,
    disable_dumpable,
    poll_once,
)
from src.bot.main import main as bot_main
from src.bot.telegram_api import TelegramClient

OWNER = 111
ALLOWED = frozenset({OWNER})


class FakeClient:
    def __init__(self, updates=None):
        self.updates = updates or []
        self.sent: list[tuple[int, str]] = []
        self.offsets: list[int | None] = []
        self.timeouts: list[int] = []

    def get_updates(self, offset, timeout):
        self.offsets.append(offset)
        self.timeouts.append(timeout)
        return self.updates

    def send_message(self, chat_id, text):
        self.sent.append((chat_id, text))


class FakeIntake:
    def __init__(self):
        self.accepted: list[tuple[int, dict]] = []

    def accept(self, chat_id, document):
        self.accepted.append((chat_id, document))
        return "접수"


def _doc_update(chat_id, update_id=1, **document):
    doc = {"file_id": "F1", "file_name": "paper.pdf", "mime_type": "application/pdf"}
    doc.update(document)
    return {
        "update_id": update_id,
        "message": {"chat": {"id": chat_id}, "document": doc},
    }


def _handle(update):
    client, intake = FakeClient(), FakeIntake()
    handle_update(update, ALLOWED, client, intake)
    return client, intake


def test_non_allowlisted_chat_gets_no_reply_and_no_download():
    client, intake = _handle(_doc_update(999))

    assert client.sent == []
    assert intake.accepted == []


def test_allowlisted_pdf_goes_to_intake_and_reply_is_its_answer():
    client, intake = _handle(_doc_update(OWNER, file_name="Lacy 2022.pdf"))

    assert [doc["file_name"] for _, doc in intake.accepted] == ["Lacy 2022.pdf"]
    assert client.sent == [(OWNER, "접수")]


def test_pdf_detected_by_extension_when_mime_is_generic():
    _, intake = _handle(
        _doc_update(OWNER, file_name="a.PDF", mime_type="application/octet-stream")
    )

    assert len(intake.accepted) == 1


def test_non_pdf_document_is_rejected():
    client, intake = _handle(
        _doc_update(OWNER, file_name="a.docx", mime_type="application/msword")
    )

    assert intake.accepted == []
    assert client.sent == [(OWNER, NOT_PDF)]


def test_pdf_over_download_limit_is_rejected_before_download():
    client, intake = _handle(_doc_update(OWNER, file_size=MAX_DOWNLOAD_BYTES + 1))

    assert intake.accepted == []
    assert client.sent == [(OWNER, TOO_LARGE)]


def test_text_message_gets_hint():
    client, _ = _handle(
        {"update_id": 1, "message": {"chat": {"id": OWNER}, "text": "안녕"}}
    )

    assert client.sent == [(OWNER, HINT)]


def test_update_without_message_is_ignored():
    client, _ = _handle({"update_id": 1, "edited_message": {"chat": {"id": OWNER}}})

    assert client.sent == []


def test_poll_once_handles_updates_and_advances_offset():
    client, intake = (
        FakeClient([_doc_update(OWNER, 5), _doc_update(999, 6)]),
        FakeIntake(),
    )

    offset = poll_once(client, ALLOWED, intake, offset=None)

    assert offset == 6 + 1
    assert client.offsets == [None]
    assert client.timeouts == [POLL_TIMEOUT_SECONDS]
    assert [chat for chat, _ in client.sent] == [OWNER]


def test_poll_once_keeps_offset_when_no_updates():
    offset = 3

    assert poll_once(FakeClient(), ALLOWED, FakeIntake(), offset=offset) == offset


def test_parse_chat_ids_accepts_commas_spaces_and_negative_ids():
    assert parse_chat_ids("111, -100222 ,") == frozenset({111, -100222})


def test_parse_chat_ids_rejects_non_numbers():
    with pytest.raises(ConfigError, match="abc"):
        parse_chat_ids("111,abc")


def test_load_config_reads_env():
    env = {"TELEGRAM_BOT_TOKEN": "t0k", "TELEGRAM_ALLOWED_CHAT_IDS": "111"}

    assert load_config(env) == BotConfig(token="t0k", allowed_chat_ids=ALLOWED)


@pytest.mark.parametrize(
    "env",
    [
        {"TELEGRAM_ALLOWED_CHAT_IDS": "111"},
        {"TELEGRAM_BOT_TOKEN": "t0k"},
        {"TELEGRAM_BOT_TOKEN": "t0k", "TELEGRAM_ALLOWED_CHAT_IDS": " , "},
    ],
)
def test_load_config_requires_token_and_nonempty_allowlist(env):
    with pytest.raises(ConfigError):
        load_config(env)


def test_main_exits_1_on_missing_config():
    assert bot_main({}) == 1


def test_bot_config_repr_hides_token():
    assert "t0k" not in repr(BotConfig(token="t0k", allowed_chat_ids=ALLOWED))


def _response(payload):
    return io.BytesIO(json.dumps(payload).encode())


def test_client_get_updates_posts_offset_and_returns_result():
    with patch(
        "src.bot.telegram_api.urlopen",
        return_value=_response({"ok": True, "result": [{"update_id": 1}]}),
    ) as urlopen:
        result = TelegramClient("t0k").get_updates(offset=4, timeout=30)

    assert result == [{"update_id": 1}]
    request = urlopen.call_args.args[0]
    assert request.full_url == "https://api.telegram.org/bott0k/getUpdates"
    assert json.loads(request.data) == {
        "offset": 4,
        "timeout": 30,
        "allowed_updates": ["message"],
    }


def test_client_send_message():
    with patch(
        "src.bot.telegram_api.urlopen",
        return_value=_response({"ok": True, "result": {}}),
    ) as urlopen:
        TelegramClient("t0k").send_message(111, "안녕")

    request = urlopen.call_args.args[0]
    assert request.full_url.endswith("/sendMessage")
    assert json.loads(request.data) == {"chat_id": 111, "text": "안녕"}


def test_client_raises_on_api_error_without_token_in_message():
    with (
        patch(
            "src.bot.telegram_api.urlopen",
            return_value=_response({"ok": False, "description": "Unauthorized"}),
        ),
        pytest.raises(RuntimeError, match="Unauthorized") as exc,
    ):
        TelegramClient("t0k").get_updates(offset=None, timeout=30)

    assert "t0k" not in str(exc.value)


def test_client_repr_hides_token():
    assert "t0k" not in repr(TelegramClient("t0k"))


def test_client_get_file_returns_file_path():
    with patch(
        "src.bot.telegram_api.urlopen",
        return_value=_response(
            {"ok": True, "result": {"file_path": "documents/a.pdf"}}
        ),
    ) as urlopen:
        path = TelegramClient("t0k").get_file("F1")

    assert path == "documents/a.pdf"
    assert json.loads(urlopen.call_args.args[0].data) == {"file_id": "F1"}


def test_client_download_file_writes_bytes(tmp_path):
    dest = tmp_path / "a.pdf"

    with patch(
        "src.bot.telegram_api.urlopen", return_value=io.BytesIO(b"%PDF-1.7 body")
    ) as urlopen:
        TelegramClient("t0k").download_file("documents/a.pdf", dest)

    assert dest.read_bytes() == b"%PDF-1.7 body"
    request = urlopen.call_args.args[0]
    assert request.full_url == "https://api.telegram.org/file/bott0k/documents/a.pdf"


def test_client_send_document_uploads_multipart(tmp_path):
    ko = tmp_path / "논문_ko.txt"
    ko.write_text("  번역문\n", encoding="utf-8")

    with patch(
        "src.bot.telegram_api.urlopen",
        return_value=_response({"ok": True, "result": {}}),
    ) as urlopen:
        TelegramClient("t0k").send_document(OWNER, ko, "번역본")

    request = urlopen.call_args.args[0]
    assert request.full_url.endswith("/sendDocument")
    assert request.get_header("Content-type").startswith(
        "multipart/form-data; boundary="
    )
    body = request.data
    assert "  번역문\n".encode() in body
    assert 'filename="논문_ko.txt"'.encode() in body
    assert b'name="chat_id"\r\n\r\n111\r\n' in body
    assert "번역본".encode() in body


class FakeLibc:
    def __init__(self, result=0):
        self.result = result
        self.calls: list[tuple[int, ...]] = []

    def prctl(self, *args):
        self.calls.append(args)
        return self.result


def test_disable_dumpable_calls_prctl_on_linux():
    libc = FakeLibc()

    assert disable_dumpable("linux", lambda: libc) is True
    assert libc.calls == [(PR_SET_DUMPABLE, 0, 0, 0, 0)]


def test_disable_dumpable_is_noop_elsewhere():
    assert disable_dumpable("darwin", FakeLibc) is False


def test_disable_dumpable_raises_when_prctl_fails():
    with pytest.raises(OSError, match="prctl"):
        disable_dumpable("linux", lambda: FakeLibc(result=-1))


def test_main_refuses_to_start_when_hardening_fails():
    env = {"TELEGRAM_BOT_TOKEN": "t0k", "TELEGRAM_ALLOWED_CHAT_IDS": "111"}

    with patch("src.bot.main.disable_dumpable", side_effect=OSError("prctl")):
        assert bot_main(env) == 1


def test_poll_once_survives_a_failing_update_and_still_advances():
    class BoomIntake(FakeIntake):
        def accept(self, chat_id, document):
            if document["file_name"] == "boom.pdf":
                raise KeyError(document["file_name"])
            return super().accept(chat_id, document)

    client = FakeClient(
        [_doc_update(OWNER, 5, file_name="boom.pdf"), _doc_update(OWNER, 6)]
    )
    intake = BoomIntake()

    offset = poll_once(client, ALLOWED, intake, offset=None)

    assert offset == 6 + 1
    assert len(intake.accepted) == 1


BLOCKED = "403 Forbidden: bot was blocked by the user"


def test_poll_once_advances_even_when_reply_fails():
    class FailingSend(FakeClient):
        def send_message(self, _chat_id, _text):
            raise OSError(BLOCKED)

    client = FailingSend([_doc_update(OWNER, 9)])
    intake = FakeIntake()

    assert poll_once(client, ALLOWED, intake, offset=None) == 9 + 1
    assert len(intake.accepted) == 1


def test_isolation_is_off_and_warned_when_not_root(tmp_path, caplog):
    assert build_isolation(tmp_path, euid=1000, pid=4321) is None
    assert "격리" in caplog.text
    assert "남은 프로세스도 정리하지 않습니다" in caplog.text


def test_non_root_pid_1_warning_does_not_claim_missing_cleanup(tmp_path, caplog):
    # As PID 1 the runner still sweeps same-UID strays after each job.
    assert build_isolation(tmp_path, euid=1000, pid=1) is None
    assert "격리" in caplog.text
    assert "정리하지 않습니다" not in caplog.text


def test_isolation_is_built_and_reset_when_root(tmp_path):
    jobs = tmp_path / "jobs"
    (jobs / "stale").mkdir(parents=True)

    template = tmp_path / "claude-home"
    (template / ".claude").mkdir(parents=True)

    iso = build_isolation(tmp_path, euid=0, jobs_dir=jobs, home_template=template)

    assert iso is not None
    assert iso.home_template == template
    assert iso.outputs_dir == tmp_path / "outputs"
    assert list(jobs.iterdir()) == []


def test_isolation_refuses_missing_home_template(tmp_path):
    # A broken image would otherwise run every job without the prod plugin.
    with pytest.raises(FileNotFoundError, match="claude-home"):
        build_isolation(
            tmp_path,
            euid=0,
            jobs_dir=tmp_path / "jobs",
            home_template=tmp_path / "claude-home",
        )


def test_main_exits_1_when_isolation_cannot_start():
    env = {"TELEGRAM_BOT_TOKEN": "t0k", "TELEGRAM_ALLOWED_CHAT_IDS": "111"}

    with (
        patch("src.bot.main.disable_dumpable", return_value=False),
        patch("src.bot.main.build_isolation", side_effect=FileNotFoundError),
        patch("src.bot.main._serve") as serve,
    ):
        assert bot_main(env) == 1
    serve.assert_not_called()
