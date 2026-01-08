# Test config constants

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING

import pytest

from src import config
from src.config import _require_env

if TYPE_CHECKING:
    from collections.abc import Callable


def test_config_constants() -> None:
    """Test that config constants are defined"""
    assert hasattr(config, "OPENAI_MODEL")
    assert hasattr(config, "TEMPERATURE")
    assert hasattr(config, "MAX_TOKEN_LENGTH")
    assert hasattr(config, "INPUT_FILE")
    assert hasattr(config, "OUTPUT_FILE")
    assert hasattr(config, "GLOSSARY_FILE")

    assert isinstance(config.MAX_TOKEN_LENGTH, int)
    assert isinstance(config.TEMPERATURE, int | float)


def test_missing_required_env_vars() -> None:
    """Test that _require_env raises ValueError when required vars are missing"""
    # Test with missing environment variables
    required: dict[str, Callable[[str], object]] = {"NONEXISTENT_VAR_12345": str}

    with pytest.raises(ValueError, match="Missing required environment variables"):
        _require_env(required)


def test_model_token_limits_fallback_to_map(monkeypatch) -> None:
    """Uses model map defaults when env overrides are absent."""
    monkeypatch.setenv("OPENAI_MODEL", "gpt-5-mini")
    monkeypatch.delenv("MODEL_CONTEXT_LENGTH", raising=False)
    monkeypatch.delenv("MODEL_MAX_OUTPUT_TOKENS", raising=False)

    importlib.reload(config)

    expected_context = 400_000
    expected_output = 128_000
    assert expected_context == config.MODEL_CONTEXT_LENGTH
    assert expected_output == config.MODEL_MAX_OUTPUT_TOKENS
