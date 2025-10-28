# Token Counter Singleton
Intent: Provide a thread-safe singleton for counting tokens with cached tiktoken encoding.

Scope: In - text token counting, threading synchronisation; Out - direct file I/O, external API calls.

Dependencies: tiktoken, threading

## Behaviour (GWT)
- AC-1: GIVEN `TokenCounter` WHEN multiple instances are requested THEN the same singleton object is returned.
- AC-2: GIVEN the first instantiation WHEN the singleton is created THEN a tiktoken encoding is loaded exactly once.
- AC-3: GIVEN later instantiations WHEN accessing the singleton THEN the previously loaded encoding is reused without reinitialising.
- AC-4: GIVEN arbitrary text WHEN `count_tokens()` is called THEN it returns a positive integer token count.
- AC-5: GIVEN an empty string WHEN `count_tokens()` is called THEN it returns zero.
- AC-6: GIVEN long repeated text WHEN `count_tokens()` runs THEN the token count grows proportionally above `MIN_TOKEN_COUNT`.
- AC-7: GIVEN repeated calls with identical input WHEN `count_tokens()` runs THEN the token count remains consistent.
- AC-8: GIVEN concurrent threads WHEN creating the singleton THEN only one instance is created due to the internal lock.
- AC-9: GIVEN text containing special characters WHEN counted THEN a positive integer is returned without errors.
- AC-10: GIVEN unicode text WHEN counted THEN a positive integer is returned without errors.
- AC-11: GIVEN multiple singleton references WHEN counting tokens THEN they share the same encoding object.

## Examples (Tabular)
| Case | Input | Steps | Expected |
|---|---|---|---|
| Singleton reuse | Instantiate twice | `TokenCounter()` → `TokenCounter()` | Same object id |
| Empty text | `""` | `count_tokens("")` | Returns `0` |
| Concurrent init | 10 threads | Instantiate in threads | Single shared instance |
| Unicode text | `"Hello 안녕하세요"` | `count_tokens(text)` | Positive integer |

## API (Summary)
TokenCounter: `count_tokens(text: str) -> int`

## Data & State
- `_instance`: `TokenCounter | None` (singleton reference)
- `_encoding`: `tiktoken.Encoding | None`
- `_lock`: `threading.Lock`

## Tracing
Spec-ID: SPEC-TOKEN-COUNTER-001
Trace-To:
- src/utils/token_counter.py (TokenCounter singleton implementation and `count_tokens`)
- tests/test_token_counter.py::TestTokenCounter::test_singleton_returns_same_instance (TEST-TOKEN-COUNTER-001-AC1)
- tests/test_token_counter.py::TestTokenCounter::test_encoding_initialized_on_first_instantiation (TEST-TOKEN-COUNTER-001-AC2)
- tests/test_token_counter.py::TestTokenCounter::test_encoding_not_reinitialized (TEST-TOKEN-COUNTER-001-AC3)
- tests/test_token_counter.py::TestTokenCounter::test_count_tokens_basic (TEST-TOKEN-COUNTER-001-AC4)
- tests/test_token_counter.py::TestTokenCounter::test_count_tokens_empty_string (TEST-TOKEN-COUNTER-001-AC5)
- tests/test_token_counter.py::TestTokenCounter::test_count_tokens_long_text (TEST-TOKEN-COUNTER-001-AC6)
- tests/test_token_counter.py::TestTokenCounter::test_count_tokens_consistency (TEST-TOKEN-COUNTER-001-AC7)
- tests/test_token_counter.py::TestTokenCounter::test_thread_safe_initialization (TEST-TOKEN-COUNTER-001-AC8)
- tests/test_token_counter.py::TestTokenCounter::test_count_tokens_with_special_characters (TEST-TOKEN-COUNTER-001-AC9)
- tests/test_token_counter.py::TestTokenCounter::test_count_tokens_with_unicode (TEST-TOKEN-COUNTER-001-AC10)
- tests/test_token_counter.py::TestTokenCounter::test_multiple_counters_share_encoding (TEST-TOKEN-COUNTER-001-AC11)
