# Translation Config
Intent: Load and manage translation settings including glossary and OpenAI parameters.

Scope: In - JSON glossary file; Out - direct file I/O and environment-backed configuration

Dependencies: openai, dotenv

## Behaviour (GWT)
- AC-1: GIVEN glossary file WHEN loading THEN JSON is parsed into string format
- AC-2: GIVEN missing file WHEN loading THEN FileNotFoundError raised
- AC-3: GIVEN required environment variables WHEN loading config THEN values are pulled from environment
- AC-4: GIVEN any required environment variable missing WHEN loading config THEN a ValueError is raised describing the missing keys

## Examples (Tabular)
| Case | Input | Steps | Expected |
|---|---|---|---|
| Load glossary | [{"term": "AI", "translation": "인공지능"}] | Load from JSON | "- AI > 인공지능" |
| Missing file | "nonexistent.json" | Load glossary | FileNotFoundError |
| Missing env | Unset required env | Instantiate TranslationConfig | ValueError listing missing keys |
| Env values | Env provides model/temp/... | Instantiate TranslationConfig | Attributes reflect env values |

## API (Summary)
TranslationConfig: _load_glossary_from_json()

## Data & State
- model: str
- temperature: float
- glossary: str
- env variables (required): OPENAI_MODEL, TEMPERATURE, MAX_TOKEN_LENGTH, INPUT_FILE, OUTPUT_FILE,
  GLOSSARY_FILE, TRANSLATION_MAX_RETRIES, TRANSLATION_RETRY_BACKOFF_SECONDS

## Tracing
Spec-ID: SPEC-CONFIG-001
