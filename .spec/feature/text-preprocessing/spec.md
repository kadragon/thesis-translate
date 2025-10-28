# Text Preprocessing
Intent: Process and prepare text from clipboard for translation, handling page numbers and cleaning text.

Scope: In - text input via clipboard, page numbering, text cleaning; Out - file I/O, direct translation

Dependencies: clipboard library, config

## Behaviour (GWT)
- AC-1: GIVEN user inputs page number WHEN running preprocessor THEN page number is set
- AC-2: GIVEN text in clipboard WHEN adding text THEN text is appended to internal buffer
- AC-3: GIVEN accumulated text WHEN cleaning text THEN lines are merged and hyphens removed
- AC-4: GIVEN cleaned text WHEN saving to file THEN text is appended with proper spacing

## Examples (Tabular)
| Case | Input | Steps | Expected |
|---|---|---|---|
| Set page | "123" | Input page number | page_number = 123 |
| Add clipboard | "Hello world" | Add from clipboard | text += "Hello world\n" |
| Clean text | "Hello -\nworld" | Clean text | text = "Hello world" |
| Save text | "Hello world" | Save to file | file appended with "  Hello world\n\n" |

## API (Summary)
TextPreprocessor: add_text_from_clipboard(), _clean_text(), run()

## Data & State
- text: str (accumulated text buffer)
- page_number: int or None

## Tracing
Spec-ID: SPEC-TEXT-PREP-001
