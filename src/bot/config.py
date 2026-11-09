"""Bot configuration from environment variables."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Mapping


class ConfigError(ValueError):
    """Raised when required bot settings are missing or malformed."""


@dataclass(frozen=True)
class BotConfig:
    token: str = field(repr=False)
    allowed_chat_ids: frozenset[int]


def parse_chat_ids(raw: str) -> frozenset[int]:
    """Parse ``"111, -100222"`` into chat IDs; blank entries are skipped."""
    ids = set()
    for part in raw.split(","):
        item = part.strip()
        if not item:
            continue
        try:
            ids.add(int(item))
        except ValueError:
            msg = f"TELEGRAM_ALLOWED_CHAT_IDS에 숫자가 아닌 값이 있습니다: {item}"
            raise ConfigError(msg) from None
    return frozenset(ids)


def load_config(env: Mapping[str, str]) -> BotConfig:
    """Build the config; the bot refuses to start without a token and allowlist."""
    token = env.get("TELEGRAM_BOT_TOKEN", "").strip()
    if not token:
        msg = "TELEGRAM_BOT_TOKEN이 설정되지 않았습니다."
        raise ConfigError(msg)
    allowed = parse_chat_ids(env.get("TELEGRAM_ALLOWED_CHAT_IDS", ""))
    if not allowed:
        msg = "TELEGRAM_ALLOWED_CHAT_IDS가 비어 있습니다."
        raise ConfigError(msg)
    return BotConfig(token=token, allowed_chat_ids=allowed)
