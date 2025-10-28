# Refactor: Remove Unreachable Return Statement

Intent: Remove unreachable code for clarity and maintainability
Scope:
- In: StreamingTranslator._translate_chunk() line 165
- Out: Logic behavior, test coverage, retry mechanism

Dependencies: None

## Behaviour (GWT)

- AC-1: GIVEN all retry paths explicitly return WHEN unreachable return removed THEN all tests remain GREEN
- AC-2: GIVEN code clarity improved WHEN developers read the method THEN no confusion about unreachable code

## Examples (Tabular)

| Exit Path | Line | Reachable | Result |
|---|---|---|---|
| Success | 163 | ✅ | return translation |
| Permanent failure | 155 | ✅ | return None |
| Retry exhausted | 149 | ✅ | return None |
| Loop completion | 165 | ❌ | return None (unreachable) |

## API (Summary)

Public surface: No changes
Internal: Remove line 165 in _translate_chunk()

## Data & State

Entities: No changes
Invariants: Retry logic, return type str | None
Migrations: N

## Tracing

Spec-ID: SPEC-REFACTOR-UNREACHABLE-001
Trace-To:
- src/core/streaming_translator.py:133-164 (_translate_chunk method - refactored)
- Tests: TEST-TRANSLATION-001-AC3, AC4, AC5, AC6

## Results (Anchored)

- Implementation: ❌ Rejected 2025-10-28
- Reason: Pre-commit hooks (ruff RET503, mypy) require explicit return statement
- Decision: Keep `return None` to satisfy linter requirements
- Lesson: While logically unreachable, Python linting standards prefer explicit returns for type safety
- Outcome: This refactoring was **not applied** - return None remains for tooling compatibility
