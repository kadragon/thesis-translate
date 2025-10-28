# config.py
OPENAI_MODEL: str = "gpt-5-mini"
TEMPERATURE: float = 1.0
MAX_TOKEN_LENGTH: int = 8000
INPUT_FILE: str = "_trimmed_text.txt"
OUTPUT_FILE: str = "_result_text_ko.txt"
GLOSSARY_FILE: str = "glossary.json"
TRANSLATION_MAX_RETRIES: int = 2
TRANSLATION_RETRY_BACKOFF_SECONDS: float = 0.0
