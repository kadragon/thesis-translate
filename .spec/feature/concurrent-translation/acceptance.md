# Acceptance Criteria - Concurrent Translation

## Acceptance Criteria

- AC-1: FileWatcher detects new content within polling interval
  - GIVEN TextPreprocessor appends 100 bytes to file
  - WHEN FileWatcher polls within 2 seconds
  - THEN new content is detected and byte offset updated

- AC-2: Translation triggered when token threshold exceeded
  - GIVEN file contains 4500 tokens (> MIN_TOKENS_FOR_TRANSLATION)
  - WHEN FileWatcher evaluates threshold
  - THEN TranslationWorker receives content for processing

- AC-3: Translation runs without blocking file monitoring
  - GIVEN TranslationWorker is processing 8000-token chunk
  - WHEN FileWatcher continues polling
  - THEN new content detection continues uninterrupted

- AC-4: Multiple batches queued correctly
  - GIVEN first translation is in progress
  - WHEN second batch exceeds threshold
  - THEN second batch is queued and processed after first completes

- AC-5: Graceful shutdown processes remaining content
  - GIVEN 2000 tokens remain untranslated (< threshold)
  - WHEN shutdown signal received
  - THEN remaining content is translated before threads exit

- AC-6: Thread-safe operations prevent data races
  - GIVEN concurrent offset updates from FileWatcher and Worker
  - WHEN lock is acquired before writes
  - THEN no offset corruption or lost updates occur

- AC-7: Metrics accurately reflect parallel operations
  - GIVEN 3 chunks translated (2 success, 1 failure) over 45 seconds
  - WHEN metrics are aggregated
  - THEN successes=2, failures=1, duration=45.0±1.0s

- AC-8: Initial state starts from offset 0
  - GIVEN no `.translation_state.json` exists
  - WHEN FileWatcher initializes
  - THEN `last_processed_offset=0` and full file is considered

- AC-9: Resume from saved state
  - GIVEN `.translation_state.json` with `last_processed_offset=5000`
  - WHEN FileWatcher initializes
  - THEN monitoring starts from byte 5000

- AC-10: Translation errors logged without crash
  - GIVEN OpenAI API returns 500 error
  - WHEN TranslationWorker catches exception
  - THEN error logged, FileWatcher continues, no process termination

## Test Strategy

**Unit Tests**:
- FileWatcher: offset tracking, threshold evaluation, state persistence
- TranslationWorker: async invocation, error handling, queue management
- ConcurrentOrchestrator: thread coordination, metrics aggregation

**Integration Tests**:
- End-to-end: TextPreprocessor → FileWatcher → TranslationWorker → output file
- Simulated concurrent writes during translation
- Graceful shutdown with pending work

**Thread Safety Tests**:
- Race condition detection using threading stress tests
- Lock contention verification
- Deadlock prevention checks

## Coverage Target

- Line Coverage: 85% (higher due to concurrency complexity)
- Branch Coverage: 75%
- Critical paths: 100% (shutdown, error handling, state persistence)

## Performance Criteria

- Polling overhead: < 1% CPU when idle
- Translation latency: ≤ 5s from threshold to translation start
- Shutdown time: < 10s to process remaining content and join threads
- Memory: No unbounded growth in queue or metrics accumulator

## DoD Checklist

- [ ] All 10 acceptance criteria pass
- [ ] Unit tests cover FileWatcher, TranslationWorker, Orchestrator independently
- [ ] Integration test demonstrates full concurrent pipeline
- [ ] Thread safety verified with race detection tools (e.g., ThreadSanitizer equivalent in Python)
- [ ] No flaky tests (run 10 times without failure)
- [ ] State persistence works across restarts
- [ ] Error scenarios handled without crashes
- [ ] Metrics include both collection and translation times
- [ ] Documentation updated in README or user guide
- [ ] Backward compatibility: existing sequential mode still works
