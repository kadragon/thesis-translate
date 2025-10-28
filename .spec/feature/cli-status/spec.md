# CLI Translation Exit Behaviour
Intent: Ensure CLI exits with distinct status when streaming translation reports partial failures.

Scope: In - `src/main.py` CLI orchestration; Out - streaming translator internals (covered elsewhere)

Dependencies: StreamingTranslator, TranslationRunResult

## Behaviour (GWT)
- AC-1: GIVEN translation completes successfully WHEN all chunks succeed THEN the CLI logs the summary and exits normally (status 0).
- AC-2: GIVEN translation completes with skipped/failed chunks WHEN summary is emitted THEN the CLI logs a warning and exits with status code 2 so automation can requeue.
- AC-3: GIVEN translation throws an unexpected exception WHEN handling the pipeline THEN the CLI logs the exception and exits with status code 1.

## Examples (Tabular)
| Case | Input | Steps | Expected |
|---|---|---|---|
| All success | metrics(successes=3, failures=0) | Run `main()` | Status 0, info log only |
| Partial failure | metrics(successes=2, failures=1) | Run `main()` | Warning logged, exit code 2 |
| Exception | `translate()` raises | Run `main()` | Exception logged, exit code 1 |

## API (Summary)
Main CLI: `main() -> None`

## Data & State
- `TranslationRunResult.failures`
- Exit codes: 0 (success), 1 (unexpected error), 2 (partial failure)

## Tracing
Spec-ID: SPEC-CLI-EXIT-001
Trace-To:
- src/main.py (main orchestration)
- tests/test_main.py::TestMain::test_main_success_flow (TEST-CLI-EXIT-001-AC1)
- tests/test_main.py::TestMain::test_main_partial_failures_warns (TEST-CLI-EXIT-001-AC2)
- tests/test_main.py::TestMain::test_main_translation_error (TEST-CLI-EXIT-001-AC3)
