# Test config constants

from src import config


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
