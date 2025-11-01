# Design Document - User-Prompted Translation

## Context

**Existing Implementation** (SPEC-CONCURRENT-TRANSLATION-001):
- FileWatcher polls file every 2s
- At 4000 tokens: automatically calls translation_callback
- User has no control over when translation starts

**User Feedback**:
- Want control over translation timing
- Prefer explicit confirmation before starting expensive translation operation
- Need visibility of accumulated tokens

**New Requirement**:
- Threshold: 40000 tokens (10x increase from 4000)
- CLI notification instead of auto-trigger
- User presses 'T' to start translation
- Sequential translations only (no concurrency)

---

## Approach

### Option 1: Notification Flag in FileWatcher (SELECTED)

**How it works**:
1. FileWatcher detects threshold → sets `_translation_ready = True`
2. TextPreprocessor checks flag in menu loop
3. Display notification in menu
4. User presses 'T' → calls `trigger_translation_manual()`
5. FileWatcher resets flag and triggers callback

**Pros**:
- Minimal changes to existing code
- FileWatcher remains responsible for threshold logic
- TextPreprocessor only handles UI
- Clean separation of concerns

**Cons**:
- Polling overhead for flag check (minimal: 1ms)
- Slight complexity in state management

### Option 2: Event-Based Notification (REJECTED)

**How it works**:
- FileWatcher emits event when threshold reached
- TextPreprocessor listens to event
- Event triggers UI update

**Pros**:
- More "reactive" design
- No polling for flag state

**Cons**:
- Adds threading complexity (event queues)
- Overkill for simple use case
- Harder to test

### Option 3: Callback with Confirmation (REJECTED)

**How it works**:
- FileWatcher calls callback with confirmation parameter
- Callback blocks and waits for user input
- User confirms, then translation proceeds

**Pros**:
- Simple conceptually

**Cons**:
- Blocks FileWatcher thread (bad design)
- CLI prompt interrupts text collection
- Hard to maintain concurrent collection

---

## Detailed Design

### Architecture Changes

```
┌─────────────────────────────────────────────────────────────────┐
│                    TextPreprocessor (CLI)                        │
│  - Menu loop checks orchestrator.is_translation_ready()         │
│  - Displays notification                                         │
│  - Handles 'T' key → trigger_translation_manual()               │
└──────────────┬──────────────────────────────────────────────────┘
               │
         ┌─────▼───────────────────────────────┐
         │ ConcurrentTranslationOrchestrator   │
         │  - Proxies to FileWatcher methods   │
         │  - Tracks is_translating state      │
         └─────┬───────────────────────────────┘
               │
      ┌────────▼──────────┐
      │   FileWatcher     │
      │  - Sets ready flag│
      │  - NO auto-trigger│
      │  - Manual trigger │
      └───────────────────┘
```

### Sequence Diagram (User-Prompted Flow)

```
User      TextPreprocessor   Orchestrator   FileWatcher   Worker
 |               |                |              |           |
 |-- Paste ----->|                |              |           |
 |               |-- append() ------------------->|           |
 |               |                |              |           |
 |               |                |  (polling)   |           |
 |               |                |  tokens=45k  |           |
 |               |                |  set _ready=True         |
 |               |                |              |           |
 |-- Menu ------>|                |              |           |
 |               |-- is_ready() ->|-- check ---->|           |
 |               |<-- (True, 45000)              |           |
 |<-- "번역 가능 (45000)"|            |              |           |
 |               |                |              |           |
 |-- Press 'T'-->|                |              |           |
 |               |-- trigger() -->|-- manual --->|           |
 |               |                |              |-- callback-> Worker
 |               |                |              |  reset flag|
 |               |                |              |  next_threshold=80k
 |               |                |              |           |
 |<-- "번역 시작" --|               |              |           |
 |               |                |  set is_translating=True |
 |               |                |              |           |
 |-- Continue -->|                |  (continue   |           |
 |   collecting  |                |   monitoring)|           |
```

### State Machine

```
┌──────────────┐
│  COLLECTING  │ <─────────────┐
│              │                │
│ ready=False  │                │
│ translating= │                │
│    False     │                │
└──────┬───────┘                │
       │ tokens >= 40000        │
       │ (FileWatcher)          │
       ▼                        │
┌──────────────┐                │
│    READY     │                │
│              │                │
│ ready=True   │                │
│ translating= │                │
│    False     │                │
└──────┬───────┘                │
       │ User presses 'T'       │
       │ (TextPreprocessor)     │
       ▼                        │
┌──────────────┐                │
│ TRANSLATING  │                │
│              │                │
│ ready=False  │                │
│ translating= │                │
│    True      │                │
└──────┬───────┘                │
       │ Translation completes  │
       │ (Worker callback)      │
       └────────────────────────┘
```

---

## Implementation Details

### Threshold Progression

**Calculation**:
```python
_next_threshold = 40000  # Initial
# After first translation
_next_threshold = 80000  # 2x
# After second translation
_next_threshold = 120000  # 3x
# Pattern: 40000 * (n + 1)
```

**Implementation**:
```python
def _advance_threshold(self) -> None:
    """Increment threshold for next notification."""
    self._next_threshold += 40000
    logger.info(f"Next threshold: {self._next_threshold} tokens")
```

### Menu Integration

**Current Menu** (TextPreprocessor):
```
===============================
A) 클립보드에서 텍스트 추가
T) 번역하기
C) 청크로 나누고 번역하기
B) 번역 완료 및 종료
===============================
선택:
```

**Enhanced Menu** (with notification):
```
===============================
A) 클립보드에서 텍스트 추가
T) 번역하기
C) 청크로 나누고 번역하기
B) 번역 완료 및 종료
===============================

[번역 가능 (45000 tokens) - 'T'를 눌러 번역 시작]

선택:
```

**Implementation**:
```python
def _display_menu(self) -> None:
    print("=" * 31)
    print("A) 클립보드에서 텍스트 추가")
    print("T) 번역하기")
    print("C) 청크로 나누고 번역하기")
    print("B) 번역 완료 및 종료")
    print("=" * 31)
    print()

    # Check translation ready status
    if hasattr(self, 'orchestrator'):
        ready, token_count = self.orchestrator.is_translation_ready()
        if ready:
            if self.orchestrator.is_translating():
                print(f"[번역 중... ({token_count} tokens 처리 완료)]")
            else:
                print(f"[번역 가능 ({token_count} tokens) - 'T'를 눌러 번역 시작]")
            print()
```

### Sequential Translation Control

**Prevent concurrent translations**:
```python
def trigger_translation_manual(self) -> bool:
    if self._is_translating:
        logger.warning("Translation already in progress")
        return False

    if not self._translation_ready:
        logger.warning("Translation not ready")
        return False

    # Set translating flag
    self._is_translating = True

    # Trigger translation
    # ... (existing logic)

    return True

def _on_translation_complete(self) -> None:
    """Callback when translation worker finishes."""
    self._is_translating = False
    logger.info("Translation completed, ready for next")
```

---

## Testing Strategy

### Unit Tests

**FileWatcher threshold logic**:
```python
def test_threshold_sets_ready_flag():
    """Verify threshold sets flag without auto-triggering."""
    watcher = FileWatcher(...)
    # Write 45000 tokens
    watcher._check_and_trigger()

    ready, count = watcher.is_translation_ready()
    assert ready is True
    assert count == 45000
    # Verify callback NOT called
    callback_mock.assert_not_called()

def test_manual_trigger_resets_flag():
    """Verify manual trigger resets flag and advances threshold."""
    watcher = FileWatcher(...)
    # Set ready
    watcher._translation_ready = True
    watcher._next_threshold = 40000

    success = watcher.trigger_translation_manual()

    assert success is True
    assert watcher._translation_ready is False
    assert watcher._next_threshold == 80000
```

**Threshold progression**:
```python
def test_threshold_increments():
    """Verify threshold increments: 40k → 80k → 120k."""
    watcher = FileWatcher(min_tokens=40000, ...)

    assert watcher._next_threshold == 40000
    watcher.trigger_translation_manual()  # First
    assert watcher._next_threshold == 80000
    watcher.trigger_translation_manual()  # Second
    assert watcher._next_threshold == 120000
```

### Integration Tests

**Full user flow**:
```python
def test_user_prompted_flow():
    """Test complete flow from collection to manual trigger."""
    # 1. Start collecting
    preprocessor = TextPreprocessor(...)
    preprocessor.start_concurrent_mode()

    # 2. Collect 45000 tokens
    # ... (simulate file writes)

    # 3. Check menu shows notification
    ready, count = preprocessor.orchestrator.is_translation_ready()
    assert ready is True
    assert count >= 40000

    # 4. User triggers translation
    success = preprocessor.handle_user_input('T')
    assert success is True

    # 5. Verify translation starts
    assert preprocessor.orchestrator.is_translating() is True
```

---

## Error Handling

### Scenarios

1. **User presses 'T' before threshold**:
   - Show: "번역할 내용이 부족합니다. (현재: 15000 tokens, 필요: 40000 tokens)"
   - No translation triggered

2. **User presses 'T' during translation**:
   - Show: "번역이 이미 진행 중입니다. 완료 후 다시 시도하세요."
   - No second translation triggered

3. **Translation fails**:
   - Show error in menu: "[번역 실패: API 오류]"
   - Reset `is_translating` flag
   - Keep content ready for retry

---

## Rollback & Migration

### Backward Compatibility

**Old Code** (auto-translate):
```python
# Existing users' code
orchestrator = ConcurrentTranslationOrchestrator(
    input_file="...",
    min_tokens=4000
)
# Works as before (auto-translates at 4000)
```

**New Code** (user-prompted):
```python
# New mode
orchestrator = ConcurrentTranslationOrchestrator(
    input_file="...",
    min_tokens=40000,
    auto_translate=False  # NEW parameter
)
# Requires user confirmation
```

**Configuration**:
```python
# config.py
AUTO_TRANSLATE_MODE = os.getenv("AUTO_TRANSLATE_MODE", "true").lower() == "true"
TRANSLATION_THRESHOLD = int(os.getenv("TRANSLATION_THRESHOLD", "4000"))
```

### Migration Guide

**For existing users**:
1. No code changes required (auto-translate is default)
2. To opt-in to user-prompted mode:
   - Set `AUTO_TRANSLATE_MODE=false`
   - Set `TRANSLATION_THRESHOLD=40000`

**For new deployments**:
- Default to user-prompted mode in future versions (v2.0)
- Document migration in CHANGELOG

---

## Performance Impact

**Added Overhead**:
- Menu loop: +1ms (flag check)
- Threshold calculation: Negligible (integer arithmetic)
- Memory: +16 bytes (4 new state variables)

**No Regression**:
- FileWatcher polling: Unchanged (2s interval)
- Translation speed: Unchanged
- Collection throughput: Unchanged

---

## Open Questions & Decisions

1. **Should we persist notification state?**
   - **Decision**: No. If user restarts, re-notify at next threshold.
   - Rationale: Simpler implementation, low impact

2. **What if user exits without translating?**
   - **Decision**: Show confirmation prompt with token count
   - Offer option to translate before exit or skip

3. **Should we support multiple thresholds simultaneously?**
   - **Decision**: No. Sequential only (one at a time)
   - Rationale: User's requirement, simpler UX

4. **Should threshold be configurable per session?**
   - **Decision**: Yes, via environment variable
   - Allows users to adjust based on document size
