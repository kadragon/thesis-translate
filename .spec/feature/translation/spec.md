# Translation
Intent: Translate thesis text chunks using OpenAI API with glossary support.

Scope: In - text file input, API calls; Out - direct file I/O, UI interactions

Dependencies: openai, tiktoken, translation_config

## Behaviour (GWT)
- AC-1: GIVEN input file WHEN translating THEN text is split into token-limited chunks
- AC-2: GIVEN text chunk WHEN translating THEN OpenAI API is called with prompt template
- AC-3: GIVEN translations WHEN processing THEN results are written to output file
- AC-4: GIVEN output file WHEN formatting THEN lines are indented properly

## Examples (Tabular)
| Case | Input | Steps | Expected |
|---|---|---|---|
| Token count | "Hello world" | Count tokens | int > 0 |
| Chunk split | Long text | Process lines | chunks created |
| API call | "Translate me" | Call OpenAI | translated string |
| Format output | "Result\n\nNext" | Format output | "  Result\n\n  Next" |

## API (Summary)
NormalTranslator: translate(), format_output(), _translate_chunk()

## Data & State
- input_file: str
- output_file: str
- max_token_length: int

## Tracing
Spec-ID: SPEC-TRANSLATION-001
