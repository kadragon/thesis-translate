# Parallel Chunk Translation

**Spec-ID**: SPEC-PARALLEL-CHUNKS-001

**Intent**: Enable concurrent processing of multiple translation chunks to reduce total translation time.

**Scope**:
- In: Parallel chunk translation using threading, configurable concurrency limit
- Out: File monitoring, complex orchestration, external async frameworks

**Dependencies**: threading (stdlib), existing StreamingTranslator, config

## Behaviour (GWT)

- **AC-1**: GIVEN multiple chunks to translate WHEN translation starts THEN up to N chunks are processed concurrently (N = configurable max_workers)
- **AC-2**: GIVEN chunks being translated in parallel WHEN a chunk completes THEN the next pending chunk starts immediately
- **AC-3**: GIVEN parallel translation in progress WHEN all chunks complete THEN results are collected in original chunk order
- **AC-4**: GIVEN a chunk fails during parallel translation WHEN max retries exhausted THEN failure is logged and other chunks continue
- **AC-5**: GIVEN parallel translation WHEN metrics are collected THEN total duration reflects parallel processing time (not sum of individual times)
- **AC-6**: GIVEN max_workers=1 WHEN translation runs THEN behavior is identical to sequential mode (backward compatible)
- **AC-7**: GIVEN parallel translation WHEN error occurs in one thread THEN other threads continue and error is reported in final metrics

## Examples (Tabular)

| Case | Chunks | max_workers | Expected Behavior |
|------|--------|-------------|-------------------|
| Parallel processing | 10 chunks | 3 | Up to 3 chunks translate simultaneously |
| Sequential fallback | 5 chunks | 1 | Chunks translate one at a time |
| Error handling | 6 chunks, 1 fails | 3 | 5 succeed, 1 fails, all reported |
| Order preservation | 4 chunks | 2 | Output maintains chunk 1,2,3,4 order |

## API (Summary)

**StreamingTranslator** (modified):
- Add `max_workers: int` parameter to `__init__` (default from config)
- Modify `translate()` to use ThreadPoolExecutor when max_workers > 1
- Keep existing `_translate_chunk()` logic unchanged

**Config additions**:
- `TRANSLATION_MAX_WORKERS`: int (default 3, min 1, max 10)

**Errors**:
- Reuses existing `TransientTranslationError`, `PermanentTranslationError`
- No new error types needed

## Data & State

- `max_workers`: int (concurrency limit from config)
- `chunk_futures`: dict[int, Future] (maps chunk_index to Future object)
- `translated_results`: dict[int, str] (maps chunk_index to translated text)
- Thread safety: ThreadPoolExecutor handles synchronization internally

## Tracing

Spec-ID: SPEC-PARALLEL-CHUNKS-001
Trace-To:
- src/core/streaming_translator.py (modified translate() method)
- src/config.py (add TRANSLATION_MAX_WORKERS)
- tests/test_parallel_chunks.py::TestParallelTranslation::test_parallel_processing (AC-1)
- tests/test_parallel_chunks.py::TestParallelTranslation::test_chunk_order_preserved (AC-3)
- tests/test_parallel_chunks.py::TestParallelTranslation::test_error_handling (AC-4, AC-7)
- tests/test_parallel_chunks.py::TestParallelTranslation::test_sequential_compatibility (AC-6)
