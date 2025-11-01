# API Specification - User-Prompted Translation

## Public Surface

### FileWatcher Extensions

**New Methods**:

```python
def is_translation_ready(self) -> tuple[bool, int]:
    """
    Check if translation is ready to be triggered by user.

    Returns:
        Tuple of (ready: bool, token_count: int)
        ready: True if accumulated tokens >= current threshold
        token_count: Number of tokens available for translation

    Thread-safe: Uses existing offset_lock
    """

def trigger_translation_manual(self) -> bool:
    """
    Manually trigger translation for accumulated content.

    Called when user presses 'T' in TextPreprocessor menu.
    Resets ready flag and advances to next threshold.

    Returns:
        bool: True if translation was triggered, False if not ready

    Side effects:
        - Calls translation_callback with accumulated content
        - Updates _next_threshold (40000 → 80000 → 120000)
        - Resets _translation_ready flag
        - Updates _last_processed_offset
    """

def get_current_threshold(self) -> int:
    """
    Get the current threshold value.

    Returns:
        int: Current threshold (40000, 80000, 120000, etc.)
    """
```

**Modified Behavior**:

```python
def _check_and_trigger(self, flush: bool = False) -> None:
    """
    Check file for new content and UPDATE READY FLAG (not auto-trigger).

    CHANGED: No longer automatically calls translation_callback
    when threshold exceeded. Instead, sets _translation_ready flag.

    Args:
        flush: If True, force translation regardless of threshold (shutdown only)
    """
```

**New State Variables**:

```python
class FileWatcher:
    _translation_ready: bool = False
    _ready_token_count: int = 0
    _next_threshold: int = 40000
    _is_translating: bool = False
```

---

### ConcurrentTranslationOrchestrator Extensions

**New Methods**:

```python
def is_translation_ready(self) -> tuple[bool, int]:
    """
    Proxy to FileWatcher.is_translation_ready().

    Returns:
        Tuple of (ready: bool, token_count: int)
    """

def trigger_translation_manual(self) -> bool:
    """
    Manually start translation.

    Returns:
        bool: True if started, False if already translating or not ready
    """

def is_translating(self) -> bool:
    """
    Check if translation is currently in progress.

    Returns:
        bool: True if translation worker is active
    """
```

---

### TextPreprocessor Integration

**Menu Display Changes**:

```python
def _display_menu(self) -> None:
    """
    Display menu with translation notification if ready.

    Menu format:
    ===============================
    A) 클립보드에서 텍스트 추가
    T) 번역하기
    C) 청크로 나누고 번역하기
    B) 번역 완료 및 종료
    ===============================

    [번역 가능 (45000 tokens) - 'T'를 눌러 번역 시작]  # If ready
    [번역 중... (45000 tokens 처리 완료)]             # If translating

    선택:
    """
```

**New Input Handler**:

```python
def _handle_translation_trigger(self) -> None:
    """
    Handle 'T' key press to start translation.

    Calls orchestrator.trigger_translation_manual()
    Displays success or error message
    """
```

**Exit Confirmation**:

```python
def _exit_with_confirmation(self) -> None:
    """
    Exit with confirmation if untranslated content remains.

    If is_translation_ready():
        Show: "20000 tokens 미번역. 번역 후 종료할까요? (Y/N)"
        Y: Trigger final translation, wait, then exit
        N: Exit without translating
    """
```

---

## Configuration Parameters

| Parameter | Type | Default | Constraints | Environment Variable |
|-----------|------|---------|-------------|----------------------|
| `INITIAL_THRESHOLD` | int | 40000 | ≥ 10000 | `TRANSLATION_INITIAL_THRESHOLD` |
| `THRESHOLD_INCREMENT` | int | 40000 | ≥ 10000 | `TRANSLATION_THRESHOLD_INCREMENT` |
| `AUTO_TRANSLATE_MODE` | bool | False | True/False | `AUTO_TRANSLATE_MODE` |

**Auto-translate mode** (backward compatibility):
- If `AUTO_TRANSLATE_MODE=True`, behaves like original (auto-trigger)
- If `AUTO_TRANSLATE_MODE=False` (default), uses user-prompted mode

---

## Error Contracts

### TranslationNotReadyError (New)
**Type**: Exception
**Raised When**: User attempts to trigger translation before threshold reached
**Retryable**: No
**Message**: "번역할 내용이 없습니다. 최소 40000 tokens이 필요합니다."

### TranslationInProgressError (New)
**Type**: Exception
**Raised When**: User attempts to trigger second translation while first is running
**Retryable**: Yes (wait for current to finish)
**Message**: "번역이 이미 진행 중입니다. 완료 후 다시 시도하세요."

---

## Thread Safety

| Resource | Protection | New Concerns |
|----------|------------|--------------|
| `_translation_ready` | `_offset_lock` | Read/write by FileWatcher and TextPreprocessor |
| `_is_translating` | `_metrics_lock` | Set by worker, read by menu |
| `_next_threshold` | `_offset_lock` | Updated on manual trigger |

---

## Backward Compatibility

**Existing Code**:
```python
# Old auto-translate mode
orchestrator = ConcurrentTranslationOrchestrator(
    input_file="...",
    output_file="...",
    config=config,
    min_tokens=4000  # Auto-triggers at 4000
)
orchestrator.run()
```

**New User-Prompted Mode**:
```python
# New user-prompted mode
orchestrator = ConcurrentTranslationOrchestrator(
    input_file="...",
    output_file="...",
    config=config,
    min_tokens=40000,  # Notifies at 40000
    auto_translate=False  # NEW: Disable auto-trigger
)
# TextPreprocessor handles user interaction
```

**Migration Path**:
- Existing users: No change (auto_translate=True by default for compatibility)
- New users: Set auto_translate=False for user-prompted mode
- Configuration file can specify preferred mode
