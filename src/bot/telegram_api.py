"""Minimal Telegram Bot API client over stdlib ``urllib``."""

from __future__ import annotations

import json
import shutil
from typing import TYPE_CHECKING, Any
from urllib.request import Request, urlopen
from uuid import uuid4

if TYPE_CHECKING:
    from pathlib import Path

_API = "https://api.telegram.org"
# Long-poll timeout plus slack so the socket outlives the server-side wait.
_SOCKET_SLACK_SECONDS = 10
_DOWNLOAD_TIMEOUT_SECONDS = 120
# Socket timeout for short calls (getFile, sendMessage); 10 s proved too tight.
_REQUEST_TIMEOUT_SECONDS = 30


class TelegramClient:
    """Calls Bot API methods. The token is kept out of reprs and error messages."""

    def __init__(self, token: str) -> None:
        self._token = token

    def __repr__(self) -> str:
        return "TelegramClient(token=***)"

    def _call(self, method: str, payload: dict[str, Any], timeout: float) -> Any:
        return self._post(
            method, json.dumps(payload).encode(), "application/json", timeout
        )

    def _post(self, method: str, data: bytes, content_type: str, timeout: float) -> Any:
        request = Request(
            f"{_API}/bot{self._token}/{method}",
            data=data,
            headers={"Content-Type": content_type},
        )
        with urlopen(request, timeout=timeout) as response:
            body = json.loads(response.read())
        if not body.get("ok"):
            msg = f"Telegram {method} 실패: {body.get('description', 'unknown error')}"
            raise RuntimeError(msg)
        return body["result"]

    def get_updates(self, offset: int | None, timeout: int) -> list[dict[str, Any]]:
        payload: dict[str, Any] = {"timeout": timeout, "allowed_updates": ["message"]}
        if offset is not None:
            payload = {"offset": offset, **payload}
        result: list[dict[str, Any]] = self._call(
            "getUpdates", payload, timeout + _SOCKET_SLACK_SECONDS
        )
        return result

    def send_message(self, chat_id: int, text: str) -> None:
        self._call(
            "sendMessage", {"chat_id": chat_id, "text": text}, _REQUEST_TIMEOUT_SECONDS
        )

    def get_file(self, file_id: str) -> str:
        """Return the server-side ``file_path`` to pass to :meth:`download_file`."""
        payload = {"file_id": file_id}
        try:
            result = self._call("getFile", payload, _REQUEST_TIMEOUT_SECONDS)
        except TimeoutError:
            # getFile is idempotent, so one retry absorbs a transient stall.
            result = self._call("getFile", payload, _REQUEST_TIMEOUT_SECONDS)
        return str(result["file_path"])

    def download_file(self, file_path: str, dest: Path) -> None:
        request = Request(f"{_API}/file/bot{self._token}/{file_path}")
        with (
            urlopen(request, timeout=_DOWNLOAD_TIMEOUT_SECONDS) as response,
            dest.open("wb") as out,
        ):
            shutil.copyfileobj(response, out)

    def send_document(self, chat_id: int, path: Path, caption: str) -> None:
        boundary = uuid4().hex
        fields = {"chat_id": str(chat_id), "caption": caption}
        parts = [
            f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"'
            f"\r\n\r\n{value}\r\n".encode()
            for name, value in fields.items()
        ]
        filename = path.name.replace('"', "_")
        parts.append(
            f"--{boundary}\r\nContent-Disposition: form-data; "
            f'name="document"; filename="{filename}"\r\n'
            "Content-Type: text/plain; charset=utf-8\r\n\r\n".encode()
            + path.read_bytes()
            + f"\r\n--{boundary}--\r\n".encode()
        )
        self._post(
            "sendDocument",
            b"".join(parts),
            f"multipart/form-data; boundary={boundary}",
            _DOWNLOAD_TIMEOUT_SECONDS,
        )
