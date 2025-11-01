# API Specification - Concurrent Translation

## Public Surface

### FileWatcher

**Purpose**: Monitor input file for changes and trigger translation when threshold exceeded.

**Class Signature**:
```python
class FileWatcher:
    def __init__(
        self,
        file_path: str,
        min_tokens: int,
        polling_interval: float,
        translation_callback: Callable[[str, int], None],
        token_counter: TokenCounter,
        state_file: str = ".translation_state.json"
    ) -> None: ...

    def start(self) -> None: ...
    def stop(self) -> None: ...
    def get_last_offset(self) -> int: ...
    def _monitor_loop(self) -> None: ...  # Internal
    def _check_and_trigger(self) -> None: ...  # Internal
    def _load_state(self) -> dict[str, Any]: ...  # Internal
    def _save_state(self) -> None: ...  # Internal
```

**Public Methods**:

- `start() -> None`
  - Starts background monitoring thread (daemon=True)
  - Thread begins polling loop immediately
  - Non-blocking; returns immediately
  - **Error**: Raises `FileWatcherError` if file_path doesn't exist

- `stop() -> None`
  - Signals shutdown via threading.Event
  - Waits for monitoring thread to join (timeout=10s)
  - Saves state to disk before exit
  - Idempotent; safe to call multiple times

- `get_last_offset() -> int`
  - Returns current byte offset in monitored file
  - Thread-safe (uses lock)
  - Used for debugging/metrics

**Configuration**:
- `min_tokens`: Default 4000, must be > 0 and < MAX_TOKEN_LENGTH
- `polling_interval`: Default 2.0 seconds, must be >= 0.5s
- `state_file`: Default `.translation_state.json`, must be writable

---

### TranslationWorker

**Purpose**: Execute translations asynchronously without blocking file monitoring.

**Class Signature**:
```python
class TranslationWorker:
    def __init__(
        self,
        translator: StreamingTranslator,
        result_queue: Queue[TranslationResult]
    ) -> None: ...

    def translate_async(self, content: str, start_offset: int) -> None: ...
    def _translate_worker(self, content: str, start_offset: int) -> None: ...  # Internal
```

**Public Methods**:

- `translate_async(content: str, start_offset: int) -> None`
  - Spawns new thread to translate `content`
  - Thread uses existing StreamingTranslator logic
  - Non-blocking; returns immediately
  - Result pushed to `result_queue` when complete
  - **Error**: Logs exceptions internally; never raises to caller

**Thread Contract**:
- Each `translate_async` call creates exactly one thread
- Thread is non-daemon (must complete before process exit)
- Thread writes result to queue atomically
- Thread logs all errors before termination

---

### ConcurrentTranslationOrchestrator

**Purpose**: Coordinate FileWatcher and TranslationWorker for end-to-end concurrent translation.

**Class Signature**:
```python
class ConcurrentTranslationOrchestrator:
    def __init__(
        self,
        input_file: str,
        output_file: str,
        config: TranslationConfig,
        min_tokens: int = 4000,
        polling_interval: float = 2.0
    ) -> None: ...

    def run(self) -> TranslationRunResult: ...
    def get_metrics(self) -> TranslationRunResult: ...
```

**Public Methods**:

- `run() -> TranslationRunResult`
  - Main entry point for concurrent mode
  - Blocks until shutdown signal (e.g., TextPreprocessor exits)
  - Returns aggregated metrics
  - **Error**: Raises `FileNotFoundError` if input_file missing
  - **Error**: Raises `FileWatcherError` if monitoring fails fatally

- `get_metrics() -> TranslationRunResult`
  - Returns real-time metrics snapshot
  - Thread-safe (uses lock)
  - Includes: successes, failures, duration_seconds
  - Can be called during `run()` for progress updates

**Integration Points**:
- Receives shutdown signal via callback or signal handler
- Writes translated chunks to `output_file` incrementally
- Calls `StreamingTranslator.format_output()` on final output

---

## Error Contracts

### FileWatcherError
**Type**: Exception
**Raised When**:
- Input file doesn't exist at initialization
- State file is corrupted (invalid JSON)
- Thread fails to start
- Unrecoverable I/O error

**Retryable**: No
**Mitigation**: Log error, exit gracefully, preserve partial state

### TransientTranslationError (Reused)
**Type**: Exception
**Raised When**: OpenAI API transient failures (rate limit, 5xx)
**Retryable**: Yes (up to max_retries)
**Behavior**: TranslationWorker handles internally; FileWatcher unaffected

### PermanentTranslationError (Reused)
**Type**: Exception
**Raised When**: OpenAI returns empty response, malformed JSON
**Retryable**: No
**Behavior**: Chunk skipped, logged in metrics.failures

---

## Rate Limits & Performance

### Polling
- **Rate**: 1 poll per `polling_interval` (default 2s)
- **Cost**: ~0.1ms per poll (file stat only)
- **SLO**: 99% of polls complete within 10ms

### Translation
- **Concurrency**: Max 1 active translation at a time (single worker thread)
- **Throughput**: ~1 chunk per 5-15s (depends on OpenAI API)
- **Backpressure**: Queue size limited to 10 pending batches

### State Persistence
- **Write Frequency**: On every threshold trigger + shutdown
- **Format**: JSON (~200 bytes)
- **Durability**: fsync after write (configurable)

---

## Thread Safety Guarantees

| Resource | Protection Mechanism | Contention Expected |
|----------|----------------------|---------------------|
| `last_processed_offset` | `threading.Lock` | Low (writer-dominant) |
| `result_queue` | `queue.Queue` (built-in) | Low (producer-consumer) |
| `state_file` | File lock (not implemented yet) | None (single writer) |
| `metrics_accumulator` | `threading.Lock` | Medium (frequent updates) |

---

## Configuration Parameters

| Parameter | Type | Default | Constraints | Environment Variable |
|-----------|------|---------|-------------|----------------------|
| `MIN_TOKENS_FOR_TRANSLATION` | int | 4000 | 1000 ≤ x < MAX_TOKEN_LENGTH | `TRANSLATION_MIN_TOKENS` |
| `POLLING_INTERVAL` | float | 2.0 | ≥ 0.5 | `TRANSLATION_POLL_INTERVAL` |
| `STATE_FILE` | str | `.translation_state.json` | Writable path | `TRANSLATION_STATE_FILE` |
| `MAX_PENDING_BATCHES` | int | 10 | ≥ 1 | `TRANSLATION_MAX_QUEUE` |

---

## Backward Compatibility

**Existing Sequential Mode**:
- `StreamingTranslator.translate()` remains unchanged
- Main CLI entry point checks for `--concurrent` flag
- Default behavior: sequential (no breaking changes)

**Migration Path**:
```python
# Old (sequential)
translator = StreamingTranslator(input_file="...")
translator.translate()

# New (concurrent)
orchestrator = ConcurrentTranslationOrchestrator(input_file="...")
orchestrator.run()
```
