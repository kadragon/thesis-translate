# Translation Config
Intent: Load and manage translation settings including glossary and OpenAI parameters.

Scope: In - JSON glossary file; Out - direct file I/O

Dependencies: openai, dotenv

## Behaviour (GWT)
- AC-1: GIVEN glossary file WHEN loading THEN JSON is parsed into string format
- AC-2: GIVEN missing file WHEN loading THEN FileNotFoundError raised

## Examples (Tabular)
| Case | Input | Steps | Expected |
|---|---|---|---|
| Load glossary | [{"term": "AI", "translation": "인공지능"}] | Load from JSON | "- AI > 인공지능" |
| Missing file | "nonexistent.json" | Load glossary | FileNotFoundError |

## API (Summary)
TranslationConfig: _load_glossary_from_json()

## Data & State
- model: str
- temperature: float
- glossary: str

## Tracing
Spec-ID: SPEC-CONFIG-001
