"""Edit the shared ``glossary.json`` from Telegram: add, list, update, delete.

Plain ``English term → 한국어`` lines (the shape of the bot's suggestion reply)
add new terms; ``/glossary``, ``/update``, and ``/delete`` list, change, and
remove entries. Terms match case-insensitively, like ``load_terms``.
"""

from __future__ import annotations

import json
import logging
import re
import threading
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger(__name__)

ARROW = "→"
# Telegram rejects messages above 4096 characters.
MAX_MESSAGE_CHARS = 4096
EMPTY = "용어집이 비어 있습니다."
NO_CHANGE = "바뀐 항목이 없습니다."
READ_FAILED = (
    "용어집 파일을 읽지 못해 아무것도 바꾸지 않았습니다. 서버에서 확인해 주세요."
)
WRITE_FAILED = (
    "용어집을 저장하지 못했습니다. 이전 내용으로 되돌렸으니 서버에서 확인해 주세요."
)
UPDATE_USAGE = "사용법: /update 영어 용어 → 새 번역어 (여러 줄 가능)"
DELETE_USAGE = "사용법: /delete 영어 용어 (여러 줄 가능)"
_COMMAND = re.compile(r"^/(\w+)(?:@(\w+))?(?:\s+|$)")
# Pasted suggestion lines may carry list markers and markdown around the text.
_LIST_MARKER = re.compile(r"^(?:[-*•]|\d+[.)])\s+")
_WRAPPERS = "`*_"

Pair = tuple[str, str]
Entry = dict[str, Any]


class GlossaryWriteError(OSError):
    """Saving failed; the previous content was put back where possible."""


def _clean(text: str) -> str:
    return text.strip().strip(_WRAPPERS).strip()


def _clean_term(text: str) -> str:
    return _clean(_LIST_MARKER.sub("", text.strip()))


def parse_pairs(text: str) -> tuple[list[Pair], list[str]]:
    """Split ``term → translation`` lines; return pairs and non-blank bad lines."""
    pairs: list[Pair] = []
    bad: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        head, sep, tail = line.partition(ARROW)
        term, translation = _clean_term(head), _clean(tail)
        if sep and term and translation:
            pairs.append((term, translation))
        else:
            bad.append(line)
    return pairs, bad


class Glossary:
    """``[{"term", "translation", ...}]`` file, rewritten in place.

    In-place writes keep the inode, so a single-file bind mount
    (``docker-compose.yml``) sees every change. Edits work on the raw list, so
    extra keys and case-only duplicates survive. Raises ``ValueError`` or
    ``OSError`` on an unreadable file before anything is written, and
    ``GlossaryWriteError`` when saving fails.

    An in-place write has a truncate-then-write window, so edits and
    :meth:`copy_to` (per-job snapshots) hold ``lock``: a job never sees a
    half-written file.
    """

    def __init__(self, path: Path) -> None:
        self.path = path
        self.lock = threading.Lock()

    def _load(self) -> tuple[list[Entry], str | None]:
        """Validated raw entries and the file text (``None`` when missing)."""
        if not self.path.is_file():
            return [], None
        text = self.path.read_text(encoding="utf-8")
        data = json.loads(text)
        if not isinstance(data, list) or not all(
            isinstance(e, dict)
            and isinstance(e.get("term"), str)
            and isinstance(e.get("translation"), str)
            for e in data
        ):
            msg = f'{self.path}: expected [{{"term": ..., "translation": ...}}]'
            raise ValueError(msg)
        return data, text

    def entries(self) -> list[Entry]:
        with self.lock:
            return self._load()[0]

    def copy_to(self, dest: Path) -> bool:
        """Write a 0644 snapshot to ``dest``; ``False`` when there is no file."""
        with self.lock:
            if not self.path.is_file():
                return False
            data = self.path.read_bytes()
        dest.write_bytes(data)
        dest.chmod(0o644)
        return True

    def _save(self, entries: list[Entry], original: str | None) -> None:
        text = json.dumps(entries, ensure_ascii=False, indent=2) + "\n"
        try:
            self.path.write_text(text, encoding="utf-8")
        except OSError as exc:
            if original is not None:
                try:
                    self.path.write_text(original, encoding="utf-8")
                except OSError:
                    logger.exception("용어집 복구 실패: %s", self.path)
            raise GlossaryWriteError(str(exc)) from exc

    @staticmethod
    def _find(entries: list[Entry], term: str) -> Entry | None:
        key = term.casefold()
        return next((e for e in entries if e["term"].casefold() == key), None)

    def add(self, pairs: list[Pair]) -> tuple[list[Pair], list[Pair]]:
        """Append new terms; return ``(added, skipped)`` with existing values."""
        with self.lock:
            return self._add(pairs)

    def _add(self, pairs: list[Pair]) -> tuple[list[Pair], list[Pair]]:
        entries, original = self._load()
        added: list[Pair] = []
        skipped: list[Pair] = []
        for term, translation in pairs:
            existing = self._find(entries, term)
            if existing:
                skipped.append((existing["term"], existing["translation"]))
                continue
            entries.append({"term": term, "translation": translation})
            added.append((term, translation))
        if added:
            self._save(entries, original)
        return added, skipped

    def update(self, pairs: list[Pair]) -> tuple[list[tuple[str, str, str]], list[str]]:
        """Change existing terms; return ``(term, old, new)`` changes and misses."""
        with self.lock:
            return self._update(pairs)

    def _update(
        self, pairs: list[Pair]
    ) -> tuple[list[tuple[str, str, str]], list[str]]:
        entries, original = self._load()
        changed: list[tuple[str, str, str]] = []
        missing: list[str] = []
        for term, translation in pairs:
            entry = self._find(entries, term)
            if entry is None:
                missing.append(term)
                continue
            changed.append((entry["term"], entry["translation"], translation))
            entry["translation"] = translation
        if changed:
            self._save(entries, original)
        return changed, missing

    def delete(self, terms: list[str]) -> tuple[list[Pair], list[str]]:
        """Remove terms; return removed pairs and misses."""
        with self.lock:
            return self._delete(terms)

    def _delete(self, terms: list[str]) -> tuple[list[Pair], list[str]]:
        entries, original = self._load()
        removed: list[Pair] = []
        missing: list[str] = []
        for term in terms:
            match = self._find(entries, term)
            if match is None:
                missing.append(term)
                continue
            entries.remove(match)
            removed.append((match["term"], match["translation"]))
        if removed:
            self._save(entries, original)
        return removed, missing

    def list_messages(self) -> list[str]:
        """All entries as messages, each within ``MAX_MESSAGE_CHARS``."""
        entries = self.entries()
        if not entries:
            return [EMPTY]
        lines = [f"{e['term']} {ARROW} {e['translation']}" for e in entries]
        return _chunk([f"용어집 {len(entries)}개:", *lines])


def _chunk(lines: list[str]) -> list[str]:
    """Join lines into messages of at most ``MAX_MESSAGE_CHARS`` each."""
    chunks: list[str] = []
    current: str | None = None
    for raw in lines:
        line = raw[:MAX_MESSAGE_CHARS]
        if current is None:
            current = line
        elif len(current) + 1 + len(line) > MAX_MESSAGE_CHARS:
            chunks.append(current)
            current = line
        else:
            current = f"{current}\n{line}"
    if current is not None:
        chunks.append(current)
    return [c for c in chunks if c.strip()]


def _section(title: str, lines: list[str]) -> list[str]:
    return [f"{title} {len(lines)}개:", *lines] if lines else []


def _join(*sections: list[str]) -> list[str]:
    lines: list[str] = []
    for section in sections:
        if section:
            lines += ([""] if lines else []) + section
    return _chunk(lines) or [NO_CHANGE]


def _fmt(pair: Pair) -> str:
    return f"{pair[0]} {ARROW} {pair[1]}"


def _add_reply(glossary: Glossary, pairs: list[Pair], bad: list[str]) -> list[str]:
    added, skipped = glossary.add(pairs)
    return _join(
        _section("추가", [_fmt(p) for p in added]),
        _section("이미 있어 건너뜀", [_fmt(p) for p in skipped]),
        _section("형식이 맞지 않아 무시", bad),
    )


def _update_reply(glossary: Glossary, body: str) -> list[str]:
    pairs, bad = parse_pairs(body)
    if not pairs:
        return [UPDATE_USAGE]
    changed, missing = glossary.update(pairs)
    return _join(
        _section("변경", [f"{t}: {old} {ARROW} {new}" for t, old, new in changed]),
        _section("용어집에 없음", missing),
        _section("형식이 맞지 않아 무시", bad),
    )


def _delete_reply(glossary: Glossary, body: str) -> list[str]:
    # Accept pasted `term → 번역어` lines too: only the term part counts.
    terms = [_clean_term(line.partition(ARROW)[0]) for line in body.splitlines()]
    terms = [t for t in terms if t]
    if not terms:
        return [DELETE_USAGE]
    removed, missing = glossary.delete(terms)
    return _join(
        _section("삭제", [_fmt(p) for p in removed]),
        _section("용어집에 없음", missing),
    )


def _for_another_bot(mention: str | None, bot_username: str | None) -> bool:
    """A ``/cmd@name`` not naming this bot; any mention when the name is unknown."""
    if mention is None:
        return False
    return bot_username is None or mention.casefold() != bot_username.casefold()


def _dispatch(
    text: str, glossary: Glossary, bot_username: str | None
) -> list[str] | None:
    command = _COMMAND.match(text)
    if command is None:
        pairs, bad = parse_pairs(text)
        return _add_reply(glossary, pairs, bad) if pairs else None
    if _for_another_bot(command.group(2), bot_username):
        # In a group, `/delete@other_bot term` is another bot's command.
        return []
    name, body = command.group(1).lower(), text[command.end() :]
    if name == "glossary":
        return glossary.list_messages()
    edit = {"update": _update_reply, "delete": _delete_reply}.get(name)
    return None if edit is None else edit(glossary, body)


def handle_glossary_messages(
    text: str, glossary: Glossary, bot_username: str | None = None
) -> list[str] | None:
    """Replies for a glossary message, or ``None`` when ``text`` is not one.

    A command addressed to another bot yields ``[]`` (handled, no reply).
    ``bot_username`` comes from ``getMe``.
    """
    try:
        return _dispatch(text, glossary, bot_username)
    except GlossaryWriteError:
        logger.exception("용어집 저장 실패: %s", glossary.path)
        return [WRITE_FAILED]
    except (OSError, ValueError):
        logger.exception("용어집 읽기 실패: %s", glossary.path)
        return [READ_FAILED]


def handle_glossary_text(
    text: str, glossary: Glossary, bot_username: str | None = None
) -> str | None:
    """Single-string form of ``handle_glossary_messages`` (joined chunks)."""
    replies = handle_glossary_messages(text, glossary, bot_username)
    return None if replies is None else "\n".join(replies)
