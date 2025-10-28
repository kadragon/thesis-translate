# Refactor: Eliminate DRY Violation in Chunk Calculation

Intent: Remove code duplication between chunk_generator and _calculate_total_chunks
Scope:
- In: StreamingTranslator.translate(), StreamingTranslator._calculate_total_chunks()
- Out: chunk_generator(), external API, test coverage

Dependencies: None

## Behaviour (GWT)

- AC-1: GIVEN existing translation workflow WHEN chunks are materialized as list THEN all existing tests pass with identical behavior
- AC-2: GIVEN _calculate_total_chunks removed WHEN translate() uses len(chunks) THEN total_chunks value remains correct
- AC-3: GIVEN refactored implementation WHEN chunking logic changes THEN only one method needs updating

## Examples (Tabular)

| Case | Before | After | Expected |
|---|---|---|---|
| Small file (3 chunks) | Two methods iterate | One method, materialized | Same chunk count & content |
| Large file | Generator + counter | Materialized list | Same chunk count & content |
| Memory usage | Lines + generator | Lines + chunks list | Acceptable increase |

## API (Summary)

Public surface: No changes
Internal: Remove _calculate_total_chunks(), modify translate() implementation

## Data & State

Entities: TranslationRunResult unchanged
Invariants: Chunk count, chunk content, success/failure metrics
Migrations: N

## Tracing

Spec-ID: SPEC-REFACTOR-DRY-001
Trace-To:
- src/core/streaming_translator.py:172-217 (translate method - refactored)
- Tests: test_normal_translator.py - all 8 tests GREEN

## Results (Anchored)

- Implementation: ✅ Completed 2025-10-28
- Code removed: 22 lines (duplicate _calculate_total_chunks method)
- Tests: All 8 existing tests pass (100% GREEN)
- Coverage: 94% on streaming_translator.py (improved from 93%)
- Memory: Acceptable increase - chunks list materialized
- Maintenance: Single source of truth for chunking logic (AC-3 satisfied)
