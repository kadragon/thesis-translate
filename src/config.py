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


_REQUIRED_VARS: dict[str, Callable[[str], object]] = {
    "INPUT_FILE": str,
    "OUTPUT_FILE": str,
}

_env_values = _require_env(_REQUIRED_VARS)

INPUT_FILE: str = _env_values["INPUT_FILE"]  # type: ignore[assignment]
OUTPUT_FILE: str = _env_values["OUTPUT_FILE"]  # type: ignore[assignment]

__all__: tuple[str, ...] = (
    "INPUT_FILE",
    "OUTPUT_FILE",
)
