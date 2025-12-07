"""Pytest configuration for env-based settings.

Trace: SPEC-CONFIG-001, TASK-20251117-01
"""

import importlib
import os
from pathlib import Path

import pytest

# Ensure required environment variables are present before modules import config.
# Values are test-friendly defaults and can be overridden within individual tests.
_TEST_ROOT = Path(__file__).parent
_DEFAULT_ENV = {
    "OPENAI_MODEL": "gpt-4.1-mini",
    "TEMPERATURE": "0.7",
    "MAX_TOKEN_LENGTH": "4000",
    "INPUT_FILE": "_trimmed_text.txt",
    "OUTPUT_FILE": "_result_text_ko.txt",
    "GLOSSARY_FILE": str(_TEST_ROOT / "test_glossary.json"),
    "TRANSLATION_MAX_RETRIES": "2",
    "TRANSLATION_RETRY_BACKOFF_SECONDS": "0.5",
    "TRANSLATION_MAX_WORKERS": "3",
    # API key left untouched to avoid clobbering real secrets; code that needs it
    # relies on the user's environment or .env file.
}

for key, value in _DEFAULT_ENV.items():
    os.environ.setdefault(key, value)

# Import src.config *after* setting default environment variables.
import src.config as cfg  # noqa: E402


@pytest.fixture(autouse=True)
def reset_config_module():
    """Ensure src.config reflects current env between tests."""
    yield
    importlib.reload(cfg)
