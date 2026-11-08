"""Pytest configuration for env-based settings.

Trace: SPEC-CONFIG-001, TASK-20251117-01
"""

import importlib
import os

import pytest

# Ensure required environment variables are present before modules import config.
# Values are test-friendly defaults and can be overridden within individual tests.
_DEFAULT_ENV = {
    "INPUT_FILE": "_trimmed_text.txt",
    "OUTPUT_FILE": "_result_text_ko.txt",
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
