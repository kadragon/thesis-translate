# GENERATED FROM SPEC-CONFIG-001

import pytest
from pathlib import Path

from src.core.translation_config import TranslationConfig


class TestTranslationConfig:
    def test_load_glossary_from_json_success(self, tmp_path):
        """AC-1: GIVEN glossary file WHEN loading THEN JSON is parsed into string format"""
        # Given
        glossary_data = [
            {"term": "artificial intelligence", "translation": "인공지능"},
            {"term": "machine learning", "translation": "기계학습"}
        ]
        glossary_file = tmp_path / "test_glossary.json"
        import json
        with open(glossary_file, 'w', encoding='utf-8') as f:
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
