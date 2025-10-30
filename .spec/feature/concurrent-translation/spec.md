# Concurrent Translation with File Monitoring

Intent: Enable parallel text collection and translation by monitoring `_trimmed_text.txt` and automatically triggering translation when sufficient content accumulates.

Scope: In - File monitoring (polling), threading, chunk-based translation triggers; Out - GUI/UI, external dependencies beyond stdlib + existing deps.

Dependencies: threading, pathlib, existing StreamingTranslator, TokenCounter

## Behaviour (GWT)

- AC-1: GIVEN TextPreprocessor writes to `_trimmed_text.txt` WHEN FileWatcher polls the file THEN it detects new content within `POLLING_INTERVAL` seconds.
- AC-2: GIVEN accumulated tokens exceed `MIN_TOKENS_FOR_TRANSLATION` WHEN FileWatcher evaluates the threshold THEN it triggers TranslationWorker with untranslated content.
- AC-3: GIVEN TranslationWorker receives content WHEN translation starts THEN it processes chunks using existing StreamingTranslator logic without blocking FileWatcher.
- AC-4: GIVEN translation is in progress WHEN more text is added THEN FileWatcher continues monitoring and queues next batch after current translation completes.
- AC-5: GIVEN TextPreprocessor exits (user presses 'B') WHEN FileWatcher detects exit signal THEN it processes remaining content and shuts down gracefully.
- AC-6: GIVEN multiple threads access shared state WHEN concurrent operations occur THEN thread-safe mechanisms (locks, queues) prevent race conditions.
- AC-7: GIVEN translation completes WHEN metrics are collected THEN total translation time and per-chunk metrics are reported separately from collection time.
- AC-8: GIVEN FileWatcher starts WHEN no previous state exists THEN it begins monitoring from file offset 0.
- AC-9: GIVEN FileWatcher resumes WHEN previous state exists THEN it continues from last processed offset to avoid duplicate translations.
- AC-10: GIVEN an error occurs in TranslationWorker WHEN FileWatcher is notified THEN it logs the error and continues monitoring without crashing.

## Examples (Tabular)

| Case | Input | Steps | Expected |
|---|---|---|---|
| Initial trigger | 5000 tokens written | FileWatcher polls every 2s | Translation triggered at first poll after threshold |
| Concurrent collection | User adds text during translation | FileWatcher continues polling | Next batch queued after current translation |
| Graceful shutdown | User exits preprocessor | Exit signal sent | Remaining content translated, threads joined |
| Thread safety | Simultaneous read/write | Lock acquisition | No data corruption or race conditions |
| Offset tracking | FileWatcher restarts | Read state file | Resume from last byte position |
| Empty file | No content yet | FileWatcher polls | No translation triggered, continues monitoring |
| Translation error | API failure in worker | Error handler invoked | Error logged, FileWatcher continues |

## API (Summary)

**FileWatcher**:
- `__init__(file_path: str, min_tokens: int, polling_interval: float, translation_callback: Callable)`
- `start() -> None`: Start monitoring thread
- `stop() -> None`: Signal shutdown and join thread
- `_monitor_loop() -> None`: Internal polling loop
- `_check_and_trigger() -> None`: Evaluate threshold and trigger translation

**TranslationWorker**:
- `__init__(translator: StreamingTranslator, output_queue: Queue)`
- `translate_async(content: str, start_offset: int) -> None`: Async translation wrapper
- `_translate_worker(content: str, start_offset: int) -> None`: Worker thread logic

**ConcurrentTranslationOrchestrator**:
- `__init__(config: TranslationConfig)`
- `run() -> TranslationRunResult`: Main entry point for concurrent mode
- `get_metrics() -> TranslationRunResult`: Aggregate metrics from all workers

Errors: Reuses `TransientTranslationError`, `PermanentTranslationError`; adds `FileWatcherError`

## Data & State

- `file_path`: str (path to `_trimmed_text.txt`)
- `min_tokens`: int (default 4000, configurable)
- `polling_interval`: float (default 2.0 seconds, configurable)
- `last_processed_offset`: int (byte position in file)
- `state_file`: str (`.translation_state.json` for persistence)
- `monitoring_thread`: Thread (daemon=True)
- `translation_queue`: Queue[tuple[str, int]] (thread-safe)
- `shutdown_event`: Event (threading primitive)
- `file_lock`: Lock (for offset updates)
- `metrics_accumulator`: dict (success/failure counts, durations)

Persistence Schema (JSON):
```json
{
  "last_processed_offset": 1234,
  "last_check_timestamp": "2025-10-30T10:30:00Z",
  "total_chunks_translated": 5
}
```

## Tracing

Spec-ID: SPEC-CONCURRENT-TRANSLATION-001
Trace-To:
- src/core/file_watcher.py (FileWatcher class, TEST-CONCURRENT-001-AC1, TEST-CONCURRENT-001-AC2)
- src/core/translation_worker.py (TranslationWorker class, TEST-CONCURRENT-001-AC3, TEST-CONCURRENT-001-AC4)
- src/core/concurrent_orchestrator.py (ConcurrentTranslationOrchestrator, TEST-CONCURRENT-001-AC5, TEST-CONCURRENT-001-AC7)
- tests/test_file_watcher.py::TestFileWatcher::test_detect_new_content (TEST-CONCURRENT-001-AC1)
- tests/test_file_watcher.py::TestFileWatcher::test_trigger_on_threshold (TEST-CONCURRENT-001-AC2)
- tests/test_translation_worker.py::TestTranslationWorker::test_async_translation (TEST-CONCURRENT-001-AC3)
- tests/test_translation_worker.py::TestTranslationWorker::test_concurrent_queueing (TEST-CONCURRENT-001-AC4)
- tests/test_concurrent_orchestrator.py::TestOrchestrator::test_graceful_shutdown (TEST-CONCURRENT-001-AC5)
- tests/test_concurrent_orchestrator.py::TestOrchestrator::test_thread_safety (TEST-CONCURRENT-001-AC6)
- tests/test_concurrent_orchestrator.py::TestOrchestrator::test_metrics_aggregation (TEST-CONCURRENT-001-AC7)
- tests/test_file_watcher.py::TestFileWatcher::test_initial_state (TEST-CONCURRENT-001-AC8)
- tests/test_file_watcher.py::TestFileWatcher::test_resume_from_offset (TEST-CONCURRENT-001-AC9)
- tests/test_translation_worker.py::TestTranslationWorker::test_error_handling (TEST-CONCURRENT-001-AC10)
