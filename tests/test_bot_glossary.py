"""Tests for glossary editing over Telegram: parsing, store, command replies."""

import json
from pathlib import Path

import pytest

from src.bot.glossary import (
    EMPTY,
    MAX_MESSAGE_CHARS,
    READ_FAILED,
    WRITE_FAILED,
    Glossary,
    handle_glossary_messages,
    handle_glossary_text,
    parse_pairs,
)


def _write(path, entries):
    path.write_text(json.dumps(entries, ensure_ascii=False), encoding="utf-8")


def _read(path):
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture
def gpath(tmp_path):
    path = tmp_path / "glossary.json"
    _write(path, [{"term": "unlearning", "translation": "언러닝"}])
    return path


def test_parse_pairs_splits_arrow_lines_and_collects_bad_lines():
    pairs, bad = parse_pairs(
        "용어집 추가 제안:\n frames of reference → 준거 틀 \n\nbroken →\n"
    )

    assert pairs == [("frames of reference", "준거 틀")]
    assert bad == ["용어집 추가 제안:", "broken →"]


def test_add_appends_new_terms_and_skips_existing_case_insensitively(gpath):
    added, skipped = Glossary(gpath).add(
        [("Unlearning", "탈학습"), ("frames of reference", "준거 틀")]
    )

    assert added == [("frames of reference", "준거 틀")]
    assert skipped == [("unlearning", "언러닝")]
    assert _read(gpath) == [
        {"term": "unlearning", "translation": "언러닝"},
        {"term": "frames of reference", "translation": "준거 틀"},
    ]


def test_add_skips_a_term_repeated_within_the_same_message(gpath):
    added, skipped = Glossary(gpath).add(
        [("deskilling", "탈숙련"), ("Deskilling", "x")]
    )

    assert added == [("deskilling", "탈숙련")]
    assert skipped == [("deskilling", "탈숙련")]


def test_write_is_in_place_utf8_and_keeps_inode(gpath):
    inode = gpath.stat().st_ino

    Glossary(gpath).add([("deskilling", "탈숙련")])

    assert gpath.stat().st_ino == inode
    assert "탈숙련" in gpath.read_text(encoding="utf-8")


def test_add_creates_missing_file(tmp_path):
    path = tmp_path / "glossary.json"

    Glossary(path).add([("deskilling", "탈숙련")])

    assert _read(path) == [{"term": "deskilling", "translation": "탈숙련"}]


def test_update_changes_existing_and_reports_missing(gpath):
    changed, missing = Glossary(gpath).update(
        [("UNLEARNING", "탈학습"), ("nothing", "없음")]
    )

    assert changed == [("unlearning", "언러닝", "탈학습")]
    assert missing == ["nothing"]
    assert _read(gpath) == [{"term": "unlearning", "translation": "탈학습"}]


def test_delete_removes_existing_and_reports_missing(gpath):
    removed, missing = Glossary(gpath).delete(["Unlearning", "nothing"])

    assert removed == [("unlearning", "언러닝")]
    assert missing == ["nothing"]
    assert _read(gpath) == []


def test_no_change_does_not_rewrite_the_file(gpath):
    before = gpath.stat().st_mtime_ns

    Glossary(gpath).delete(["nothing"])

    assert gpath.stat().st_mtime_ns == before


def test_malformed_file_is_never_overwritten(gpath):
    gpath.write_text("{not json", encoding="utf-8")

    reply = handle_glossary_text("deskilling → 탈숙련", Glossary(gpath))

    assert reply == READ_FAILED
    assert gpath.read_text(encoding="utf-8") == "{not json"


def test_plain_text_without_arrow_is_not_a_glossary_message(gpath):
    assert handle_glossary_text("안녕", Glossary(gpath)) is None


def test_plain_arrow_lines_add_and_reply_lists_added_and_skipped(gpath):
    reply = handle_glossary_text(
        "frames of reference → 준거 틀\nunlearning → 탈학습", Glossary(gpath)
    )

    assert reply is not None
    assert "추가 1개" in reply
    assert "frames of reference → 준거 틀" in reply
    assert "이미 있어 건너뜀 1개" in reply
    assert "unlearning → 언러닝" in reply


def test_glossary_command_lists_entries(gpath):
    reply = handle_glossary_text("/glossary", Glossary(gpath))

    assert reply == "용어집 1개:\nunlearning → 언러닝"


def test_glossary_command_accepts_own_bot_mention_case_insensitively(gpath):
    reply = handle_glossary_text(
        "/glossary@Thesis_Bot", Glossary(gpath), bot_username="thesis_bot"
    )

    assert reply is not None
    assert "unlearning → 언러닝" in reply


@pytest.mark.parametrize("username", ["thesis_bot", None])
def test_command_addressed_to_another_bot_gets_no_reply_and_no_write(gpath, username):
    before = gpath.read_bytes()

    for text in ("/delete@other_bot unlearning", "/glossary@other_bot", "/x@other"):
        replies = handle_glossary_messages(text, Glossary(gpath), bot_username=username)
        assert replies == []

    assert gpath.read_bytes() == before


def test_edits_hold_the_lock(gpath, monkeypatch):
    glossary = Glossary(gpath)
    seen: list[bool] = []
    real_load = Glossary._load

    def spy(self):
        seen.append(self.lock.locked())
        return real_load(self)

    monkeypatch.setattr(Glossary, "_load", spy)
    glossary.add([("forgetting", "망각")])
    glossary.update([("forgetting", "잊기")])
    glossary.delete(["forgetting"])

    assert seen == [True, True, True]
    assert not glossary.lock.locked()


def test_copy_to_writes_a_snapshot_under_the_lock(gpath, tmp_path, monkeypatch):
    glossary = Glossary(gpath)
    dest = tmp_path / "job" / "glossary.json"
    dest.parent.mkdir()
    held: list[bool] = []
    real = Path.read_bytes

    def spy(self):
        if self == gpath:
            held.append(glossary.lock.locked())
        return real(self)

    monkeypatch.setattr(Path, "read_bytes", spy)

    assert glossary.copy_to(dest) is True

    assert held == [True]
    assert not dest.is_symlink()
    assert dest.read_bytes() == real(gpath)


def test_copy_to_skips_a_missing_glossary(tmp_path):
    dest = tmp_path / "copy.json"

    assert Glossary(tmp_path / "missing.json").copy_to(dest) is False
    assert not dest.exists()


def test_glossary_command_on_empty_glossary(tmp_path):
    assert handle_glossary_text("/glossary", Glossary(tmp_path / "g.json")) == EMPTY


def test_long_glossary_is_split_under_the_message_limit(tmp_path):
    path = tmp_path / "g.json"
    count = 300
    _write(
        path,
        [{"term": f"term {i}", "translation": "번역어" * 10} for i in range(count)],
    )

    reply = Glossary(path).list_messages()

    assert len(reply) > 1
    assert all(len(chunk) <= MAX_MESSAGE_CHARS for chunk in reply)
    assert sum(chunk.count("→") for chunk in reply) == count


def test_update_command_changes_and_reports(gpath):
    reply = handle_glossary_text(
        "/update unlearning → 탈학습\nnothing → 없음", Glossary(gpath)
    )

    assert reply is not None
    assert "unlearning: 언러닝 → 탈학습" in reply
    assert "nothing" in reply
    assert _read(gpath)[0]["translation"] == "탈학습"


def test_update_command_without_pairs_shows_usage(gpath):
    reply = handle_glossary_text("/update", Glossary(gpath))

    assert reply is not None
    assert "/update" in reply


def test_delete_command_removes_lines_of_terms(gpath):
    reply = handle_glossary_text("/delete unlearning\nnothing", Glossary(gpath))

    assert reply is not None
    assert "unlearning → 언러닝" in reply
    assert "nothing" in reply
    assert _read(gpath) == []


def test_delete_command_accepts_pasted_arrow_lines(gpath):
    handle_glossary_text("/delete unlearning → 언러닝", Glossary(gpath))

    assert _read(gpath) == []


def test_unknown_command_is_not_handled(gpath):
    assert handle_glossary_text("/start", Glossary(gpath)) is None


def test_edit_replies_are_split_under_the_message_limit(tmp_path):
    path = tmp_path / "g.json"
    count = 50
    _write(path, [{"term": f"t{i}", "translation": "가" * 100} for i in range(count)])
    text = "/delete " + "\n".join(f"t{i}" for i in range(count))

    replies = handle_glossary_messages(text, Glossary(path))

    assert replies is not None
    assert len(replies) > 1
    assert all(len(chunk) <= MAX_MESSAGE_CHARS for chunk in replies)
    assert _read(path) == []


def test_write_failure_restores_file_and_says_save_failed(gpath, monkeypatch, caplog):
    original = gpath.read_text(encoding="utf-8")
    real_write = Path.write_text
    calls = []

    def failing_write(self, data, *args, **kwargs):
        calls.append(data)
        if len(calls) == 1:
            real_write(self, data[:5], *args, **kwargs)
            raise OSError(28, "No space left on device")
        return real_write(self, data, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", failing_write)

    reply = handle_glossary_text("deskilling → 탈숙련", Glossary(gpath))

    assert reply == WRITE_FAILED
    assert gpath.read_text(encoding="utf-8") == original
    assert "용어집" in caplog.text


def test_edits_keep_extra_keys_and_case_duplicates(tmp_path):
    path = tmp_path / "g.json"
    entries = [
        {"term": "unlearning", "translation": "언러닝", "note": "keep"},
        {"term": "Unlearning", "translation": "탈학습"},
    ]
    _write(path, entries)

    Glossary(path).add([("deskilling", "탈숙련")])

    assert _read(path) == [*entries, {"term": "deskilling", "translation": "탈숙련"}]


def test_parse_pairs_strips_list_markers_and_markdown():
    pairs, bad = parse_pairs(
        "- **frames of reference** → 준거 틀\n1. `deskilling` → `탈숙련`\n• a → *가*"
    )

    assert pairs == [
        ("frames of reference", "준거 틀"),
        ("deskilling", "탈숙련"),
        ("a", "가"),
    ]
    assert bad == []


def test_delete_strips_markdown_from_terms(gpath):
    handle_glossary_text("/delete - **unlearning**", Glossary(gpath))

    assert _read(gpath) == []
