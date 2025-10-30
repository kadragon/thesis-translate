# User-Prompted Translation with CLI Notification

Intent: Replace automatic translation trigger with user confirmation prompt, allowing users to control when translation starts while maintaining concurrent text collection.

Scope: In - CLI notification, user prompt integration, threshold notification; Out - Automatic translation, GUI notifications, multiple concurrent translations.

Dependencies: TextPreprocessor, FileWatcher, ConcurrentTranslationOrchestrator (from SPEC-CONCURRENT-TRANSLATION-001)

## Behaviour (GWT)

- AC-1: GIVEN accumulated tokens reach threshold (40000) WHEN FileWatcher detects THEN it notifies TextPreprocessor without auto-starting translation.
- AC-2: GIVEN translation is ready WHEN TextPreprocessor displays menu THEN it shows "번역 가능 (45000 tokens) - 'T'를 눌러 번역 시작".
- AC-3: GIVEN user presses 'T' WHEN translation is ready THEN translation starts for accumulated content.
- AC-4: GIVEN user ignores notification WHEN more tokens accumulate to next threshold (80000, 120000...) THEN notification updates with new token count.
- AC-5: GIVEN translation is in progress WHEN threshold reached again THEN new notification waits until current translation completes.
- AC-6: GIVEN translation completes WHEN new content exceeds threshold THEN new notification appears.
- AC-7: GIVEN user presses 'B' (finish) WHEN untranslated content remains THEN it asks for confirmation before final translation.

## Examples (Tabular)

| Case | Input | Steps | Expected |
|---|---|---|---|
| First threshold | 45000 tokens collected | FileWatcher sets ready flag | Menu shows "번역 가능 (45000 tokens)" |
| User starts translation | User presses 'T' | Orchestrator triggers translation | Translation starts, menu shows "번역 중..." |
| Ignore first threshold | User continues collecting | 80000 tokens reached | Menu updates "번역 가능 (80000 tokens)" |
| Translation in progress | 40000 more tokens while translating | Threshold reached | No new notification until current done |
| Sequential completion | First translation done, 50000 new tokens | Check threshold | New notification appears |
| Exit with pending | User presses 'B', 20000 tokens untranslated | Exit confirmation | "20000 tokens 미번역. 번역 후 종료할까요?" |

## API (Summary)

**FileWatcher Extensions**:
- `get_translation_ready() -> tuple[bool, int]`: Check if translation ready, return (ready, token_count)
- `reset_ready_flag() -> None`: Clear ready flag after user starts translation
- `_next_threshold: int`: Track next notification threshold (40000, 80000, 120000...)

**TextPreprocessor Integration**:
- Check `orchestrator.is_translation_ready()` in menu loop
- Display notification in menu
- Handle 'T' key for translation trigger
- Show "번역 중..." status during translation

**Orchestrator Extensions**:
- `is_translation_ready() -> tuple[bool, int]`: Proxy to FileWatcher
- `trigger_translation_manual() -> None`: Start translation on user command
- `is_translating() -> bool`: Check if translation in progress

## Data & State

**New State Variables**:
- `_translation_ready: bool` - Translation can start
- `_ready_token_count: int` - Tokens available for translation
- `_next_threshold: int` - Next notification point (40000, 80000, 120000...)
- `_is_translating: bool` - Translation currently running
- `_last_notified_threshold: int` - Last threshold we notified about

**State Transitions**:
```
COLLECTING -> READY (threshold reached)
READY -> TRANSLATING (user presses 'T')
TRANSLATING -> COLLECTING (translation complete)
COLLECTING -> READY (next threshold reached)
```

## Tracing

Spec-ID: SPEC-USER-PROMPTED-001
Trace-To:
- SPEC-CONCURRENT-TRANSLATION-001 (extends)
- tests/test_user_prompted_translation.py
- src/core/file_watcher.py (extensions)
- src/utils/text_preprocessor.py (menu integration)
