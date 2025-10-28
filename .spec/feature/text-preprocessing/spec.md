# Text Preprocessing
Intent: Process and prepare text from clipboard for translation, handling page numbers and cleaning text.

Scope: In - text input via clipboard, page numbering, text cleaning; Out - file I/O, direct translation

Dependencies: clipboard library, config

## Behaviour (GWT)
- AC-1: GIVEN user inputs page number WHEN running preprocessor THEN page number is set
- AC-2: GIVEN text in clipboard WHEN adding text THEN text is appended to internal buffer
- AC-3: GIVEN accumulated text WHEN cleaning text THEN lines are merged and hyphens removed
- AC-4: GIVEN cleaned text WHEN saving to file via Translate command THEN text is appended with single indentation ("  ") and trailing blank line
- AC-5: GIVEN Translate-and-clean command `"C"` WHEN executed THEN the cleaned text is written exactly once with single indentation (no double prefix) and the local buffer is cleared
- AC-6: GIVEN clipboard access raises an exception WHEN adding text THEN a warning is logged and the buffer remains unchanged while the loop continues
- AC-7: GIVEN cleaning raises an exception WHEN normalising text THEN a warning is logged and the user is prompted to retry without crashing

## Examples (Tabular)
| Case | Input | Steps | Expected |
|---|---|---|---|
| Set page | "123" | Input page number | page_number = 123 |
| Add clipboard | "Hello world" | Add from clipboard | text += "Hello world\n" |
| Clean text | "Hello -\nworld" | Clean text | text = "Hello world" |
| Save translate | "Hello world" | Command Enter | file appended with "  Hello world\n\n" |
| Save translate+clean | "Hello\nworld" | Command "C" | file appended with "  Hello world\n\n" |
| Clipboard failure | Exception | Paste triggers error | Warning logged, buffer unchanged |

## API (Summary)
TextPreprocessor: add_text_from_clipboard(), _clean_text(), run()

## Data & State
- text: str (accumulated text buffer)
- page_number: int or None

## Tracing
Spec-ID: SPEC-TEXT-PREP-001
Trace-To:
- src/utils/text_preprocessor.py (TextPreprocessor.run/add_text_from_clipboard/_clean_text/add_text_to_file)
- tests/test_text_preprocessor.py::TestTextPreprocessor::test_run_add_text_flow (TEST-TEXT-PREP-001-AC1)
- tests/test_text_preprocessor.py::TestTextPreprocessor::test_add_text_from_clipboard (TEST-TEXT-PREP-001-AC2)
- tests/test_text_preprocessor.py::TestTextPreprocessor::test_clean_text (TEST-TEXT-PREP-001-AC3)
- tests/test_text_preprocessor.py::TestTextPreprocessor::test_add_text_to_file (TEST-TEXT-PREP-001-AC4)
- tests/test_text_preprocessor.py::TestTextPreprocessor::test_run_translate_flow (TEST-TEXT-PREP-001-AC4)
- tests/test_text_preprocessor.py::TestTextPreprocessor::test_run_translate_clean_flow (TEST-TEXT-PREP-001-AC5)
- tests/test_text_preprocessor.py::TestTextPreprocessor::test_add_text_from_clipboard_error (TEST-TEXT-PREP-001-AC6)
- tests/test_text_preprocessor.py::TestTextPreprocessor::test_clean_text_error (TEST-TEXT-PREP-001-AC7)
