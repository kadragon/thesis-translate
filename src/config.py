"""Configuration sourced strictly from environment variables.

Trace: SPEC-CONFIG-001, TASK-20251117-01
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from dotenv import load_dotenv

if TYPE_CHECKING:
    from collections.abc import Callable

load_dotenv()


def _cast(value: str, caster: Callable[[str], object], name: str) -> object:
    try:
        return caster(value)
    except Exception as exc:  # pragma: no cover - branch exercised via ValueError path
        msg = f"Environment variable {name} is invalid: {exc}"
        raise ValueError(msg) from exc


def _require_env(required: dict[str, Callable[[str], object]]) -> dict[str, object]:
    missing = [key for key in required if not os.getenv(key)]
    if missing:
        missing_str = ", ".join(missing)
        msg = f"Missing required environment variables: {missing_str}"
        raise ValueError(msg)

    values: dict[str, object] = {}
    for key, caster in required.items():
        raw = os.getenv(key)
        assert raw is not None  # for type checkers; guarded by missing check above
        values[key] = _cast(raw, caster, key)
    return values


def _optional_int_env(name: str, default: int | None) -> int | None:
    raw = os.getenv(name)
    if raw is None:
        return default
    value = _cast(raw, int, name)
    assert isinstance(value, int)
    return value


_REQUIRED_VARS: dict[str, Callable[[str], object]] = {
    "OPENAI_MODEL": str,
    "TEMPERATURE": float,
    "MAX_TOKEN_LENGTH": int,
    "INPUT_FILE": str,
    "OUTPUT_FILE": str,
    "GLOSSARY_FILE": str,
    "TRANSLATION_MAX_RETRIES": int,
    "TRANSLATION_RETRY_BACKOFF_SECONDS": float,
    "TRANSLATION_MAX_WORKERS": int,
}

_env_values = _require_env(_REQUIRED_VARS)

OPENAI_MODEL: str = _env_values["OPENAI_MODEL"]  # type: ignore[assignment]
TEMPERATURE: float = _env_values["TEMPERATURE"]  # type: ignore[assignment]
MAX_TOKEN_LENGTH: int = _env_values["MAX_TOKEN_LENGTH"]  # type: ignore[assignment]
INPUT_FILE: str = _env_values["INPUT_FILE"]  # type: ignore[assignment]
OUTPUT_FILE: str = _env_values["OUTPUT_FILE"]  # type: ignore[assignment]
GLOSSARY_FILE: str = _env_values["GLOSSARY_FILE"]  # type: ignore[assignment]
TRANSLATION_MAX_RETRIES: int = _env_values["TRANSLATION_MAX_RETRIES"]  # type: ignore[assignment]
TRANSLATION_RETRY_BACKOFF_SECONDS: float = _env_values[
    "TRANSLATION_RETRY_BACKOFF_SECONDS"
]  # type: ignore[assignment]
_raw_max_workers = _env_values["TRANSLATION_MAX_WORKERS"]
assert isinstance(_raw_max_workers, int)
TRANSLATION_MAX_WORKERS: int = max(1, min(10, _raw_max_workers))

_MODEL_TOKEN_LIMITS: dict[str, tuple[int, int]] = {
    "gpt-5-mini": (400_000, 128_000),
}
_model_limits = _MODEL_TOKEN_LIMITS.get(OPENAI_MODEL)
_default_context = _model_limits[0] if _model_limits else None
_default_max_output = _model_limits[1] if _model_limits else None

MODEL_CONTEXT_LENGTH = _optional_int_env("MODEL_CONTEXT_LENGTH", _default_context)
MODEL_MAX_OUTPUT_TOKENS = _optional_int_env(
    "MODEL_MAX_OUTPUT_TOKENS", _default_max_output
)

__all__: tuple[str, ...] = (
    "GLOSSARY_FILE",
    "INPUT_FILE",
    "MAX_TOKEN_LENGTH",
    "MODEL_CONTEXT_LENGTH",
    "MODEL_MAX_OUTPUT_TOKENS",
    "OPENAI_MODEL",
    "OUTPUT_FILE",
    "TEMPERATURE",
    "TRANSLATION_MAX_RETRIES",
    "TRANSLATION_MAX_WORKERS",
    "TRANSLATION_RETRY_BACKOFF_SECONDS",
)
