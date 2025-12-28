# Project Memory

## Recent Changes (Compacted)

- 2025-12-28 (SPEC-REFACTOR-DEDUP-001): Created `_write_translations()` and `_update_task_progress()` helpers to deduplicate sequential/parallel paths. Reduced overlap from 70% to <30%. 80 tests, 100% coverage.

- 2025-12-28 (SPEC-REFACTOR-VALIDATION-001): Added `NoOpProgress` class for null-safe progress handling. Removed conditional checks in streaming logic. 74 tests, 100% coverage.

- 2025-12-28 (SPEC-REFACTOR-EXCEPTIONS-001): Merged `TransientTranslationError` and `PermanentTranslationError` into single `TranslationError(is_transient: bool)`. 69 tests, 100% coverage.

- 2025-12-28 (SPEC-REFACTOR-COVERAGE-001): Added pragma to `if __name__ == "__main__"` guard. Achieved 100% coverage.

- 2025-12-28 (SPEC-REFACTOR-CONSTANTS-001): Extracted magic numbers to class constants: `API_TIMEOUT_SECONDS`, `ESTIMATED_OUTPUT_TOKEN_RATIO`, `KOREAN_CHAR_TO_TOKEN_RATIO`, `CONFIG_INDENT`.

- 2025-12-26 (SPEC-RICH-UX-001): Unified rich console UX for progress and logging via shared RichHandler.

- 2025-12-24 (SPEC-BALANCED-CHUNKS-001): Implemented 3-phase balanced chunk distribution. ~20% reduction in parallel translation time.

- 2025-12-07 (SPEC-PARALLEL-CHUNKS-001): Added ThreadPoolExecutor with `TRANSLATION_MAX_WORKERS` (default 3). Removed file monitoring features.

- 2025-12-02: Migrated task tracking to YAML format (backlog.yaml, current.yaml, done.yaml).

- 2025-11-17 (SPEC-CONFIG-001): Config reads from environment only; missing keys raise ValueError.

## Task Management

### Format Standards

- **backlog.yaml**: Pending tasks under `pending_tasks:` list
- **current.yaml**: Single active task under `current_task:` (null when none)
- **done.yaml**: Completed tasks under `completed_tasks:` list with 2-space indentation

### YAML Rules

1. List items use 2-space indentation under parent key
2. Properties use 4-space indentation
3. Multi-line strings use `|` indicator

## Key Patterns Learned

- **NoOp handler pattern**: Use for optional dependencies to eliminate null checks
- **Helper extraction**: Extract common ops from similar code paths into focused helpers
- **Boolean flags over class hierarchy**: Prefer `is_transient` flag over separate exception types
- **Pragma for entry points**: Standard practice for `if __name__ == "__main__"` guards

---

## Compaction Summary

- **Date**: 2025-12-28
- **Keep count (N)**: 10
- **Trace**: SDD-CONTEXT-COMPACTOR-001

### Removed Items

- **backlog.yaml**: 3 duplicate tasks removed (already in done.yaml)
- **done.yaml**: 6 old tasks removed (kept 10 most recent), verbose entries condensed
- **.spec/**: 7 unreferenced specs deleted:
  - refactoring/refactoring-plan.md
  - feature/cli-status/spec.md
  - feature/text-preprocessing/spec.md
  - feature/token-counter/spec.md
  - feature/translation/spec.md
  - refactor/dry-chunking/spec.md
  - refactor/remove-unreachable/spec.md
- **memory.md**: Verbose paragraphs condensed to bullet points

### Final Counts

- backlog.yaml: 0 pending tasks
- done.yaml: 10 completed tasks (was 16)
- .spec/: 9 specs (was 16)
- memory.md: ~60 lines (was 46 lines with verbose text)
