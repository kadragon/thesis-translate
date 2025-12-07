"""Pytest configuration for env-based settings.

Trace: SPEC-CONFIG-001, SPEC-PARALLEL-CHUNKS-001, TASK-20251117-01, TASK-20251207-02
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
    # Safe test default so OpenAI client can instantiate during unit tests.
    # setdefault() ensures we never override a real secret in the caller env.
    "OPENAI_API_KEY": "test-api-key",
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
