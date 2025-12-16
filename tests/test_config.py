# Test config constants

from __future__ import annotations

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
