# Balanced Chunk Distribution

**Spec-ID**: SPEC-BALANCED-CHUNKS-001

**Intent**: Improve parallel translation efficiency by distributing text into evenly-sized chunks instead of greedy sequential chunking.

**Scope**:
- In: Balanced chunk generation algorithm, pre-scanning total tokens, uniform distribution
- Out: Sentence splitting, semantic analysis, multi-pass optimization

**Dependencies**: existing TokenCounter, chunk_generator method

## Problem Statement

Current greedy chunking creates unbalanced chunks (e.g., 19,592 vs 8,115 tokens). In parallel processing, the largest chunk determines total completion time, leading to underutilized worker threads.

## Behaviour (GWT)

- **AC-1**: GIVEN a text that requires multiple chunks WHEN chunk_generator is called THEN total tokens are calculated first before chunking
- **AC-2**: GIVEN total tokens and max_token_length WHEN calculating num_chunks THEN num_chunks = ceil(total_tokens / max_token_length)
- **AC-3**: GIVEN num_chunks calculated WHEN distributing text THEN target_chunk_size = total_tokens / num_chunks (balanced)
- **AC-4**: GIVEN lines being accumulated into chunks WHEN a chunk reaches approximately target_chunk_size THEN the chunk is finalized at next line boundary
- **AC-5**: GIVEN balanced chunking WHEN all chunks are created THEN variance between chunk sizes is minimized (no chunk should be < 70% of target_chunk_size unless it's the last chunk)
- **AC-6**: GIVEN a single line exceeding max_token_length WHEN chunking THEN it is yielded as a standalone chunk (edge case handling maintained)
- **AC-7**: GIVEN balanced chunking WHEN total tokens < max_token_length THEN single chunk is created (no change from current behavior)

## Examples (Tabular)

| Total Tokens | max_token_length | num_chunks | target_chunk_size | Expected Distribution |
|--------------|------------------|------------|-------------------|----------------------|
| 27,707 | 20,000 | 2 | ~13,853 | [~13,853, ~13,854] |
| 45,000 | 20,000 | 3 | ~15,000 | [~15,000, ~15,000, ~15,000] |
| 15,000 | 20,000 | 1 | 15,000 | [15,000] |
| 60,000 | 20,000 | 3 | ~20,000 | [~20,000, ~20,000, ~20,000] |

## API (Summary)

**StreamingTranslator.chunk_generator** (modified):
- Phase 1: Pre-scan all lines to calculate total tokens
- Phase 2: Calculate num_chunks and target_chunk_size
- Phase 3: Accumulate lines targeting balanced distribution
- Signature remains unchanged: `chunk_generator(lines: list[str]) -> Iterator[tuple[int, str]]`

**Algorithm sketch**:
```python
# Phase 1: Calculate total tokens
total_tokens = sum(count_tokens(line) for line in lines)

# Phase 2: Calculate target
num_chunks = ceil(total_tokens / max_token_length)
target_chunk_size = total_tokens / num_chunks

# Phase 3: Distribute lines into chunks
# Accumulate lines until current_chunk_tokens >= target_chunk_size
# Finalize chunk at line boundary
```

## Data & State

- `total_tokens`: int (sum of all line tokens)
- `num_chunks`: int (required number of chunks)
- `target_chunk_size`: float (ideal tokens per chunk)
- `current_chunk_tokens`: int (accumulated tokens in current chunk)
- `chunks_created`: int (counter for completed chunks)

## Performance Impact

**Before** (greedy): [19,592, 8,115] → parallel time = max(107s, 65s) = 107s
**After** (balanced): [~13,853, ~13,853] → parallel time ≈ 86s
**Expected improvement**: ~20% reduction in parallel translation time

## Tracing

Spec-ID: SPEC-BALANCED-CHUNKS-001
Trace-To:
- src/core/streaming_translator.py::chunk_generator (modified)
- tests/test_streaming_translator.py::test_balanced_chunk_distribution (AC-1 to AC-5)
- tests/test_streaming_translator.py::test_balanced_single_chunk (AC-7)
- tests/test_streaming_translator.py::test_balanced_oversized_line (AC-6)
