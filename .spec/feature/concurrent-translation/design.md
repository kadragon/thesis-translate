# Design Document - Concurrent Translation

## Context

**Existing Structure**:
- TextPreprocessor: Interactive CLI collecting text from clipboard → `_trimmed_text.txt`
- StreamingTranslator: Sequential chunking + translation of entire file after collection completes
- Current bottleneck: User waits idle during translation (5-10 minutes for large thesis)

**Problem**:
- Translation throughput: ~1 chunk per 10s (OpenAI API latency)
- Text collection throughput: ~1 paragraph per 5s (human speed)
- Zero parallelism: collection fully blocks until previous step completes

**Constraint**:
- Cannot use external dependencies (watchdog, asyncio refactor)
- Must preserve existing StreamingTranslator logic (tested, proven)
- Must remain compatible with sequential mode

---

## Approach

### Option 1: Polling with Threading (SELECTED)

**Pros**:
- No external dependencies (stdlib only: threading, queue)
- Simple mental model: one monitor thread + worker threads
- Low overhead: <1% CPU when idle
- Deterministic behavior (no event-driven complexity)
- Easy to test (time.sleep mocking)

**Cons**:
- Slight latency (up to polling_interval before trigger)
- Thread coordination overhead (locks, queues)

**Decision Rationale**: Meets requirements with minimal complexity. Polling interval of 2s is acceptable for human-driven text collection.

### Option 2: Watchdog Library (REJECTED)

**Pros**:
- Instant notification of file changes
- OS-level file system events

**Cons**:
- External dependency (against project constraints)
- Overkill for this use case
- Adds debugging complexity (event handler edge cases)

### Option 3: Asyncio Refactor (REJECTED)

**Pros**:
- Modern Python concurrency
- No thread coordination complexity

**Cons**:
- Major refactor of StreamingTranslator (high risk)
- Mixing async/sync in TextPreprocessor (CLI is sync)
- Steeper learning curve for contributors

---

## Detailed Design

### Architecture (C4 Level 3)

```
┌─────────────────────────────────────────────────────────────────────┐
│                       ConcurrentTranslationOrchestrator             │
│  - Initializes FileWatcher + TranslationWorker                     │
│  - Handles shutdown signal from TextPreprocessor                    │
│  - Aggregates metrics from result_queue                             │
└───────────────────┬─────────────────────────┬───────────────────────┘
                    │                         │
          ┌─────────▼──────────┐    ┌────────▼──────────┐
          │   FileWatcher      │    │ TranslationWorker │
          │  (Monitor Thread)  │    │  (Worker Threads) │
          └─────────┬──────────┘    └────────┬──────────┘
                    │                        │
         ┌──────────▼─────────────┐ ┌───────▼──────────────┐
         │  _trimmed_text.txt     │ │ StreamingTranslator  │
         │  (File System)         │ │ (Existing Logic)     │
         └────────────────────────┘ └──────────┬───────────┘
                                               │
                                    ┌──────────▼───────────┐
                                    │ _result_text_ko.txt  │
                                    │ (Incremental Writes) │
                                    └──────────────────────┘
```

### Sequence Diagram

```
User          TextPreprocessor   FileWatcher    TranslationWorker   StreamingTranslator
 |                   |                |                 |                    |
 |-- Paste text ---->|                |                 |                    |
 |                   |-- append() --->|                 |                    |
 |                   |                |-- poll() ------>|                    |
 |                   |                |  (every 2s)     |                    |
 |                   |                |<-- stat() ------|                    |
 |                   |                |                 |                    |
 |                   |                |-- tokens>4000?  |                    |
 |                   |                |     YES         |                    |
 |                   |                |-- callback() -->|                    |
 |                   |                |                 |-- spawn thread --->|
 |                   |                |                 |                    |
 |-- Paste more ---->|                |                 |                    |
 |                   |-- append() --->|                 |                    |-- translate_chunk()
 |                   |                |-- poll() ------>|                    |    (in progress)
 |                   |                |  (continues)    |                    |
 |                   |                |                 |<-- result ---------|
 |                   |                |                 |-- push queue ----->|
 |                   |                |<-- next batch --|                    |
 |                   |                |                 |                    |
 |-- Press 'B' ----->|                |                 |                    |
 |                   |-- signal() --->|                 |                    |
 |                   |                |-- stop() ------>|                    |
 |                   |                |                 |-- join threads --->|
 |                   |                |<-- metrics -----|                    |
 |<-- Done ----------|<-- return -----|                 |                    |
```

---

## Data Flow

### 1. Initialization
```
Orchestrator.run()
  ├─> Load state from .translation_state.json (if exists)
  ├─> Initialize FileWatcher(min_tokens=4000, polling=2.0)
  ├─> Initialize TranslationWorker(translator=StreamingTranslator)
  └─> Start monitoring thread (daemon=True)
```

### 2. Monitoring Loop (FileWatcher Thread)
```python
while not shutdown_event.is_set():
    current_size = os.stat(file_path).st_size
    if current_size > last_processed_offset:
        new_content = read_from_offset(file_path, last_processed_offset)
        token_count = token_counter.count_tokens(new_content)

        if token_count >= min_tokens:
            translation_callback(new_content, last_processed_offset)
            with lock:
                last_processed_offset = current_size
            save_state()

    time.sleep(polling_interval)
```

### 3. Translation Trigger (Worker Thread)
```python
def translation_callback(content: str, offset: int):
    worker.translate_async(content, offset)
    # Returns immediately; translation runs in background

def translate_async(content: str, offset: int):
    thread = Thread(target=_translate_worker, args=(content, offset))
    thread.start()
    # Thread writes to result_queue when done
```

### 4. Result Collection (Orchestrator)
```python
while True:
    try:
        result = result_queue.get(timeout=1.0)
        metrics.successes += result.successes
        metrics.failures += result.failures
        append_to_output(result.translated_text)
    except Empty:
        if shutdown_event.is_set() and no_active_threads():
            break
```

---

## State Management

### Persistence Schema
```json
{
  "version": "1.0",
  "last_processed_offset": 12345,
  "last_check_timestamp": "2025-10-30T10:30:00Z",
  "total_chunks_translated": 8,
  "total_tokens_processed": 64000
}
```

**Write Triggers**:
- After each successful translation trigger
- On graceful shutdown
- On fatal error (before exit)

**Recovery Scenarios**:
1. **Process killed**: Resume from last_processed_offset on restart
2. **File deleted**: Detect via FileNotFoundError, reset to offset=0
3. **State corrupted**: Log warning, fallback to offset=0

---

## Thread Coordination

### Synchronization Primitives

| Primitive | Purpose | Held By | Contention Risk |
|-----------|---------|---------|-----------------|
| `offset_lock: Lock` | Protect `last_processed_offset` | FileWatcher, Worker | Low (short critical section) |
| `result_queue: Queue` | Transfer translation results | Worker → Orchestrator | None (lock-free queue) |
| `shutdown_event: Event` | Signal graceful shutdown | Orchestrator → All | None (read-only after set) |
| `active_threads: list` | Track worker threads | Orchestrator | Low (append + join only) |

### Deadlock Prevention
- **Lock Ordering**: Always acquire `offset_lock` before `metrics_lock`
- **Timeout Policy**: All `.get()` calls use timeout to avoid indefinite blocking
- **Thread Types**: Monitor thread is daemon; worker threads are non-daemon (must complete)

### Graceful Shutdown Protocol
```python
1. shutdown_event.set()  # Signal all threads
2. FileWatcher exits monitor_loop (checks shutdown_event each iteration)
3. Orchestrator calls worker.join(timeout=10s) for each active thread
4. Remaining content (< min_tokens) translated in main thread
5. Final metrics aggregated from result_queue
6. State saved to disk
7. Exit with code 0 (success) or 2 (partial failure)
```

---

## Error Handling

### Error Categories

| Error Type | Example | Recovery Strategy |
|------------|---------|-------------------|
| **Transient** | OpenAI 429 rate limit | Retry in worker (up to max_retries) |
| **Permanent** | Empty API response | Skip chunk, log in metrics.failures |
| **Fatal** | File deleted mid-process | Save state, exit gracefully with code 1 |
| **Thread Crash** | Unexpected exception in worker | Catch all, log traceback, continue monitoring |

### Logging Strategy
```python
# FileWatcher
logger.info(f"Detected {tokens} new tokens at offset {offset}")
logger.debug(f"Poll cycle completed in {duration}ms")

# TranslationWorker
logger.info(f"Translation started for chunk at offset {offset}")
logger.error(f"Translation failed: {exc}", exc_info=True)

# Orchestrator
logger.info(f"Metrics: {successes}/{total} chunks succeeded")
logger.warning(f"Shutdown timeout; forcing thread termination")
```

---

## Performance Considerations

### Overhead Analysis

**Polling Cost** (per cycle):
- `os.stat()`: ~0.1ms
- Token counting: ~2ms per 1000 tokens (tiktoken)
- Lock acquisition: ~0.01ms
- **Total**: ~2.1ms per cycle (0.1% CPU at 2s interval)

**Memory Footprint**:
- FileWatcher: ~50KB (thread stack)
- TranslationWorker: ~100KB per active thread
- Result queue: ~10KB per pending result (max 10 = 100KB)
- **Total**: ~250KB overhead

**Latency Breakdown**:
- Detection latency: 0 to `polling_interval` (average: 1s)
- Queue latency: <1ms (in-memory)
- Translation latency: 5-15s (OpenAI API, unchanged)
- **Total added latency**: ~1s on average (acceptable)

### Optimization Opportunities (Future)

1. **Adaptive Polling**: Increase interval when no activity detected
2. **Batch Writes**: Accumulate multiple results before writing to output
3. **Parallel Workers**: Allow N concurrent translations (needs API quota check)
4. **Token Caching**: Cache token counts for unchanged content

---

## Rollback & Fallback

### Rollback Plan
If concurrent mode introduces regressions:
1. Add `--sequential` flag to force old behavior
2. Document known issues in CHANGELOG
3. Fix root cause in patch release
4. Remove flag once stable

### Feature Flag
```python
# In config.py
ENABLE_CONCURRENT_TRANSLATION = os.getenv("CONCURRENT_MODE", "false") == "true"

# In main.py
if ENABLE_CONCURRENT_TRANSLATION:
    orchestrator = ConcurrentTranslationOrchestrator(...)
    orchestrator.run()
else:
    translator = StreamingTranslator(...)
    translator.translate()
```

### Backward Compatibility Test Suite
- Run existing `test_normal_translator.py` with both modes
- Verify output files are identical (byte-for-byte)
- Check metrics match within ±5% tolerance (timing variance)

---

## Testing Strategy

### Unit Tests (Per Component)

**FileWatcher**:
- Mock `os.stat()` to simulate file growth
- Mock `time.sleep()` to speed up tests
- Verify offset updates are atomic (race condition test)

**TranslationWorker**:
- Mock `StreamingTranslator` to return canned responses
- Inject exceptions to test error handling
- Verify result_queue receives all results

**Orchestrator**:
- Mock FileWatcher and TranslationWorker
- Test shutdown signal propagation
- Verify metrics aggregation correctness

### Integration Tests

**End-to-End**:
1. Start TextPreprocessor in subprocess
2. Simulate user input via stdin
3. Monitor `_result_text_ko.txt` for incremental writes
4. Send SIGINT to trigger shutdown
5. Verify final output matches expected

**Concurrency Stress Test**:
1. Write to `_trimmed_text.txt` at high frequency (100 writes/sec)
2. Verify no offset corruption
3. Verify no lost translations
4. Verify no thread leaks (check `threading.active_count()`)

### Property-Based Tests (Optional)

Use `hypothesis` to generate:
- Random file write patterns (offset, size)
- Random polling intervals (0.5s to 5s)
- Random token counts (0 to 20000)

Invariants:
- `last_processed_offset` ≤ `file_size`
- `total_tokens_processed` = sum of all chunk tokens
- No duplicate translations

---

## Migration & Deployment

### Deployment Checklist
- [ ] Add feature flag to config.py
- [ ] Update CLI argparse with `--concurrent` option
- [ ] Add .translation_state.json to .gitignore
- [ ] Document new mode in README.md
- [ ] Add troubleshooting guide for common issues

### User Migration
**For existing users**:
1. Update to new version (backward compatible)
2. Existing workflows unchanged (sequential default)
3. Opt-in via `--concurrent` flag
4. Verify output quality before full adoption

**For new users**:
1. Install from pypi (or local)
2. Run `python -m thesis_translate --concurrent`
3. Monitor logs for errors
4. Report issues via GitHub

---

## Open Questions

1. **Should we support multiple concurrent workers?**
   - Current design: 1 worker at a time (simple, safe)
   - Alternative: N workers (faster, but OpenAI rate limits?)
   - **Decision**: Start with 1, add N in future if needed

2. **How to handle TextPreprocessor integration?**
   - Option A: Modify TextPreprocessor to signal Orchestrator
   - Option B: Run TextPreprocessor in subprocess, monitor exit
   - **Decision**: Option B (less coupling, easier testing)

3. **Should state file be human-readable JSON or binary?**
   - JSON: Easy debugging, ~200 bytes
   - Binary (pickle): Smaller, ~100 bytes
   - **Decision**: JSON (transparency > size for this use case)

4. **What happens if user edits `_trimmed_text.txt` manually?**
   - Current: Offset tracking assumes append-only
   - Risk: Editing middle of file breaks offset logic
   - **Mitigation**: Document assumption, add integrity check (file size only increases)
