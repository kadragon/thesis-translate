"""Per-update logic: allowlist gate, document checks, hand-off to intake."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from collections.abc import Set as AbstractSet

logger = logging.getLogger(__name__)

PDF_MIME = "application/pdf"
# Bot API getFile refuses files above 20 MB.
MAX_DOWNLOAD_BYTES = 20 * 1024 * 1024
HINT = "번역할 논문 PDF 파일을 보내 주세요."
NOT_PDF = "PDF 파일만 번역할 수 있습니다."
TOO_LARGE = "20 MB를 넘는 파일은 받을 수 없습니다(Telegram 봇 제한)."


class Sender(Protocol):
    def send_message(self, chat_id: int, text: str) -> None: ...


class Acceptor(Protocol):
    def accept(self, chat_id: int, document: dict[str, Any]) -> str: ...


def _is_pdf(document: dict[str, Any]) -> bool:
    name = str(document.get("file_name") or "")
    return document.get("mime_type") == PDF_MIME or name.lower().endswith(".pdf")


def handle_update(
    update: dict[str, Any],
    allowed: AbstractSet[int],
    client: Sender,
    intake: Acceptor,
) -> None:
    """Reply to one update. Chats outside ``allowed`` are dropped silently.

    The allowlist check comes before anything else — no download, no reply
    (AGENTS.md golden principle 2).
    """
    message = update.get("message")
    if not isinstance(message, dict):
        return
    chat_id = message.get("chat", {}).get("id")
    if chat_id not in allowed:
        logger.info("허용되지 않은 채팅의 메시지를 무시했습니다: %s", chat_id)
        return
    document = message.get("document")
    if not isinstance(document, dict):
        client.send_message(chat_id, HINT)
    elif not _is_pdf(document):
        client.send_message(chat_id, NOT_PDF)
    elif (document.get("file_size") or 0) > MAX_DOWNLOAD_BYTES:
        client.send_message(chat_id, TOO_LARGE)
    else:
        client.send_message(chat_id, intake.accept(chat_id, document))
