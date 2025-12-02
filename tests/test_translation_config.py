# GENERATED FROM SPEC-CONFIG-001


import importlib
import json

import pytest

import src.config as config_module
from src.core.translation_config import TranslationConfig


class TestTranslationConfig:
    def test_load_glossary_from_json_success(self, tmp_path):
        """AC-1: GIVEN glossary file WHEN loading THEN JSON is parsed into
        string format"""
        # Given
        glossary_data = [
            {"term": "artificial intelligence", "translation": "인공지능"},
            {"term": "machine learning", "translation": "기계학습"},
        ]
        glossary_file = tmp_path / "test_glossary.json"

        with glossary_file.open("w", encoding="utf-8") as f:
            json.dump(glossary_data, f)

        # When
        config = TranslationConfig(glossary_path=str(glossary_file))

        # Then
        expected = "- artificial intelligence > 인공지능\n- machine learning > 기계학습"
        assert config.glossary == expected

    def test_load_glossary_from_json_missing_file(self):
        """AC-2: GIVEN missing file WHEN loading THEN FileNotFoundError raised"""
        # Given
        missing_file = "nonexistent.json"

        # When/Then
        with pytest.raises(FileNotFoundError):
            TranslationConfig(glossary_path=missing_file)

    def test_env_values_are_loaded_and_cast(self, monkeypatch, tmp_path):
        """AC-3: Environment variables are loaded and cast correctly."""
        # Given
        glossary_file = tmp_path / "glossary.json"
        json.dump(
            [{"term": "AI", "translation": "인공지능"}],
            glossary_file.open("w", encoding="utf-8"),
        )

        overrides = {
            "OPENAI_MODEL": "gpt-test",
            "TEMPERATURE": "0.55",
            "MAX_TOKEN_LENGTH": "1234",
            "INPUT_FILE": "input.txt",
            "OUTPUT_FILE": "output.txt",
            "GLOSSARY_FILE": str(glossary_file),
            "TRANSLATION_MAX_RETRIES": "5",
            "TRANSLATION_RETRY_BACKOFF_SECONDS": "1.5",
        }

        for key, value in overrides.items():
            monkeypatch.setenv(key, value)

        # When
        importlib.reload(config_module)

        # Then
        assert config_module.OPENAI_MODEL == "gpt-test"
        expected_temp = 0.55
        expected_max_tokens = 1234
        assert (
            isinstance(config_module.TEMPERATURE, float)
            and expected_temp == config_module.TEMPERATURE
        )
        assert expected_max_tokens == config_module.MAX_TOKEN_LENGTH
        assert config_module.INPUT_FILE == "input.txt"
        assert config_module.OUTPUT_FILE == "output.txt"
        expected_retries = 5
        expected_backoff = 1.5
        assert str(glossary_file) == config_module.GLOSSARY_FILE
        assert expected_retries == config_module.TRANSLATION_MAX_RETRIES
        assert expected_backoff == config_module.TRANSLATION_RETRY_BACKOFF_SECONDS
        # Re-instantiate TranslationConfig to confirm glossary still loads via env path.
        config = TranslationConfig()
        assert "AI" in config.glossary

    def test_missing_env_raises_value_error(self, monkeypatch):
        """AC-4: Missing required environment variable raises ValueError."""
        for key in [
            "OPENAI_MODEL",
            "TEMPERATURE",
            "MAX_TOKEN_LENGTH",
            "INPUT_FILE",
            "OUTPUT_FILE",
            "GLOSSARY_FILE",
            "TRANSLATION_MAX_RETRIES",
            "TRANSLATION_RETRY_BACKOFF_SECONDS",
        ]:
            monkeypatch.delenv(key, raising=False)

        with pytest.raises(ValueError) as excinfo:
            importlib.reload(config_module)

        assert "Missing required environment variables" in str(excinfo.value)
