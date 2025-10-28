# Streaming Translation
Intent: Stream chunked thesis translations through OpenAI Chat Completions with glossary-aware prompts.

Scope: In - UTF-8 text files, OpenAI Chat Completions, glossary formatting; Out - CLI prompts, UI.

Dependencies: openai, tiktoken, translation_config

## Behaviour (GWT)
- AC-1: GIVEN an input file WHEN `translate()` runs THEN lines are accumulated into token-bounded chunks using `TokenCounter.count_tokens` and chunk totals are logged before processing.
- AC-2: GIVEN chunk iteration WHEN `chunk_generator()` is invoked THEN it yields `(chunk_index, chunk_text)` in deterministic order and logs each chunk boundary.
- AC-3: GIVEN a prepared chunk WHEN `_translate_chunk()` executes THEN it builds the prompt from `TranslationConfig.PROMPT_TEMPLATE` + glossary and calls `OpenAI.chat.completions.create`.
- AC-4: GIVEN the OpenAI call fails WHEN `_translate_chunk()` handles the exception THEN it raises `TransientTranslationError` for retryable errors, otherwise `PermanentTranslationError`.
- AC-5: GIVEN retries remain WHEN `_translate_chunk()` raises `TransientTranslationError` THEN the retry loop logs the attempt, sleeps the configured backoff (0 for tests), and replays up to `max_retries`.
- AC-6: GIVEN max retries are exceeded WHEN a chunk still fails THEN the translator logs the failure, records it in metrics, and skips writing that chunk.
- AC-7: GIVEN chunk translations succeed WHEN `translate()` writes output THEN it emits each translated chunk separated by blank lines to the configured output path.
- AC-8: GIVEN `format_output()` is invoked WHEN formatting completes THEN every non-empty line in the output file is left-padded with two spaces for consistent indentation.
- AC-9: GIVEN the input file cannot be opened WHEN `translate()` starts THEN it raises `FileNotFoundError` and logs the missing path.
- AC-10: GIVEN translation completes WHEN metrics are summarised THEN success/failed counts and elapsed seconds are logged and returned.

## Examples (Tabular)
| Case | Input | Steps | Expected |
|---|---|---|---|
| Chunk sizing | Paragraphs exceeding `max_token_length` | Count tokens, flush buffer | Chunk count increments and logs total |
| Chunk generation | Lines that exceed token limit | Call `chunk_generator()` | Deterministic `(index, text)` yielded |
| Prompt assembly | Chunk "Hello" | `_translate_chunk()` | API called with rendered prompt and glossary |
| Retry exhaustion | API raises transient error repeatedly | Run translate with `max_retries=2` | Logged failures, chunk skipped |
| Metrics | 3 chunks (2 success, 1 failed) | Run translate | Metrics shows successes=2, failures=1 |
| Missing input | Invalid path | Call `translate()` | `FileNotFoundError` raised, no output written |
| Formatting | File with uneven indentation | Call `format_output()` | Each non-empty line prefixed with two spaces |

## API (Summary)
StreamingTranslator: `translate()`, `chunk_generator()`, `_invoke_model()` (internal), `_translate_chunk()` (with retry), `format_output()`
Errors: `TransientTranslationError`, `PermanentTranslationError`
Metrics: `TranslationRunResult(successes: int, failures: int, duration_seconds: float)`

## Data & State
- `client`: OpenAI
- `config`: `TranslationConfig` (model, temperature, glossary string, prompt template)
- `token_counter`: `TokenCounter` singleton
- `input_file`: str (UTF-8 path)
- `output_file`: str (UTF-8 path)
- `max_token_length`: int
- `max_retries`: int (default 2)
- `retry_backoff_seconds`: float (default 0.0 for CLI)
- `logger`: chunk/metrics logs

## Tracing
Spec-ID: SPEC-TRANSLATION-001
Trace-To:
- src/core/streaming_translator.py (StreamingTranslator.translate/_translate_chunk/format_output)
- tests/test_normal_translator.py::TestTranslator::test_translate_success (TEST-TRANSLATION-001-AC1, TEST-TRANSLATION-001-AC7)
- tests/test_normal_translator.py::TestTranslator::test_chunk_generator_deterministic (TEST-TRANSLATION-001-AC2)
- tests/test_normal_translator.py::TestTranslator::test_translate_chunk_success (TEST-TRANSLATION-001-AC3)
- tests/test_normal_translator.py::TestTranslator::test_translate_chunk_retry_transient (TEST-TRANSLATION-001-AC4, TEST-TRANSLATION-001-AC5)
- tests/test_normal_translator.py::TestTranslator::test_translate_chunk_retry_exhausted (TEST-TRANSLATION-001-AC6)
- tests/test_normal_translator.py::TestTranslator::test_format_output (TEST-TRANSLATION-001-AC8)
- tests/test_normal_translator.py::TestTranslator::test_translate_file_not_found (TEST-TRANSLATION-001-AC9)
- tests/test_normal_translator.py::TestTranslator::test_translate_metrics_logging (TEST-TRANSLATION-001-AC10)
