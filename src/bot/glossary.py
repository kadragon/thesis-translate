"""Edit the shared ``glossary.json`` from Telegram: add, list, update, delete.

Plain ``English term → 한국어`` lines (the shape of the bot's suggestion reply)
add new terms; ``/glossary``, ``/update``, and ``/delete`` list, change, and
remove entries. Terms match case-insensitively, like ``load_terms``.
"""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING

from src.core.alignment import load_terms

if TYPE_CHECKING:
    from pathlib import Path

ARROW = "→"
# Telegram rejects messages above 4096 characters.
MAX_MESSAGE_CHARS = 4096
EMPTY = "용어집이 비어 있습니다."
READ_FAILED = (
    "용어집 파일을 읽지 못해 아무것도 바꾸지 않았습니다. 서버에서 확인해 주세요."
)
UPDATE_USAGE = "사용법: /update 영어 용어 → 새 번역어 (여러 줄 가능)"
DELETE_USAGE = "사용법: /delete 영어 용어 (여러 줄 가능)"
_COMMAND = re.compile(r"^/(\w+)(?:@\w+)?(?:\s+|$)")

Pair = tuple[str, str]


def parse_pairs(text: str) -> tuple[list[Pair], list[str]]:
    """Split ``term → translation`` lines; return pairs and non-blank bad lines."""
    pairs: list[Pair] = []
    bad: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        term, sep, translation = (part.strip() for part in line.partition(ARROW))
        if sep and term and translation:
            pairs.append((term, translation))
        else:
            bad.append(line)
    return pairs, bad


class Glossary:
    """``[{"term", "translation"}]`` file, rewritten in place.

    In-place writes keep the inode, so a single-file bind mount
    (``docker-compose.yml``) sees every change. Raises ``ValueError`` or
    ``OSError`` on an unreadable file before anything is written.
    """

    def __init__(self, path: Path) -> None:
        self.path = path

    def entries(self) -> list[dict[str, str]]:
        return load_terms([self.path])

    def _save(self, entries: list[dict[str, str]]) -> None:
        text = json.dumps(entries, ensure_ascii=False, indent=2) + "\n"
        self.path.write_text(text, encoding="utf-8")

    def add(self, pairs: list[Pair]) -> tuple[list[Pair], list[Pair]]:
        """Append new terms; return ``(added, skipped)`` with existing values."""
        entries = self.entries()
        index = {e["term"].casefold(): e for e in entries}
        added: list[Pair] = []
        skipped: list[Pair] = []
        for term, translation in pairs:
            existing = index.get(term.casefold())
            if existing:
                skipped.append((existing["term"], existing["translation"]))
                continue
            entry = {"term": term, "translation": translation}
            entries.append(entry)
            index[term.casefold()] = entry
            added.append((term, translation))
        if added:
            self._save(entries)
        return added, skipped

    def update(self, pairs: list[Pair]) -> tuple[list[tuple[str, str, str]], list[str]]:
        """Change existing terms; return ``(term, old, new)`` changes and misses."""
        entries = self.entries()
        index = {e["term"].casefold(): e for e in entries}
        changed: list[tuple[str, str, str]] = []
        missing: list[str] = []
        for term, translation in pairs:
            entry = index.get(term.casefold())
            if entry is None:
                missing.append(term)
                continue
            changed.append((entry["term"], entry["translation"], translation))
            entry["translation"] = translation
        if changed:
            self._save(entries)
        return changed, missing

    def delete(self, terms: list[str]) -> tuple[list[Pair], list[str]]:
        """Remove terms; return removed pairs and misses."""
        entries = self.entries()
        removed: list[Pair] = []
        missing: list[str] = []
        for term in terms:
            key = term.casefold()
            match = next((e for e in entries if e["term"].casefold() == key), None)
            if match is None:
                missing.append(term)
                continue
            entries.remove(match)
            removed.append((match["term"], match["translation"]))
        if removed:
            self._save(entries)
        return removed, missing

    def list_messages(self) -> list[str]:
        """All entries as messages, each within ``MAX_MESSAGE_CHARS``."""
        entries = self.entries()
        if not entries:
            return [EMPTY]
        lines = [f"{e['term']} {ARROW} {e['translation']}" for e in entries]
        chunks: list[str] = []
        current = f"용어집 {len(entries)}개:"
        for line in lines:
            if len(current) + 1 + len(line) > MAX_MESSAGE_CHARS:
                chunks.append(current)
                current = line
            else:
                current = f"{current}\n{line}"
        chunks.append(current)
        return chunks


def _section(title: str, lines: list[str]) -> list[str]:
    return [f"{title} {len(lines)}개:", *lines] if lines else []


def _join(*sections: list[str]) -> str:
    return "\n\n".join("\n".join(s) for s in sections if s) or "바뀐 항목이 없습니다."


def _fmt(pair: Pair) -> str:
    return f"{pair[0]} {ARROW} {pair[1]}"


def _add_reply(glossary: Glossary, pairs: list[Pair], bad: list[str]) -> str:
    added, skipped = glossary.add(pairs)
    return _join(
        _section("추가", [_fmt(p) for p in added]),
        _section("이미 있어 건너뜀", [_fmt(p) for p in skipped]),
        _section("형식이 맞지 않아 무시", bad),
    )


def _update_reply(glossary: Glossary, body: str) -> str:
    pairs, bad = parse_pairs(body)
    if not pairs:
        return UPDATE_USAGE
    changed, missing = glossary.update(pairs)
    return _join(
        _section("변경", [f"{t}: {old} {ARROW} {new}" for t, old, new in changed]),
        _section("용어집에 없음", missing),
        _section("형식이 맞지 않아 무시", bad),
    )


def _delete_reply(glossary: Glossary, body: str) -> str:
    # Accept pasted `term → 번역어` lines too: only the term part counts.
    terms = [
        line.partition(ARROW)[0].strip() for line in body.splitlines() if line.strip()
    ]
    terms = [t for t in terms if t]
    if not terms:
        return DELETE_USAGE
    removed, missing = glossary.delete(terms)
    return _join(
        _section("삭제", [_fmt(p) for p in removed]),
        _section("용어집에 없음", missing),
    )


def _dispatch(text: str, glossary: Glossary) -> list[str] | None:
    command = _COMMAND.match(text)
    if command is None:
        pairs, bad = parse_pairs(text)
        return [_add_reply(glossary, pairs, bad)] if pairs else None
    name, body = command.group(1).lower(), text[command.end() :]
    if name == "glossary":
        return glossary.list_messages()
    edit = {"update": _update_reply, "delete": _delete_reply}.get(name)
    return None if edit is None else [edit(glossary, body)]


def handle_glossary_messages(text: str, glossary: Glossary) -> list[str] | None:
    """Replies for a glossary message, or ``None`` when ``text`` is not one."""
    try:
        return _dispatch(text, glossary)
    except (OSError, ValueError):
        return [READ_FAILED]


def handle_glossary_text(text: str, glossary: Glossary) -> str | None:
    """Single-string form of ``handle_glossary_messages`` (joined chunks)."""
    replies = handle_glossary_messages(text, glossary)
    return None if replies is None else "\n".join(replies)
