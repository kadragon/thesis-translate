# Acceptance Criteria - User-Prompted Translation

## Acceptance Criteria

- AC-1: FileWatcher notifies without auto-translation
  - GIVEN accumulated tokens reach 40000
  - WHEN FileWatcher evaluates content
  - THEN it sets ready flag WITHOUT calling translation_callback

- AC-2: CLI displays translation notification
  - GIVEN _translation_ready flag is True with 45000 tokens
  - WHEN TextPreprocessor displays menu
  - THEN menu shows "번역 가능 (45000 tokens) - 'T'를 눌러 번역 시작"

- AC-3: User triggers translation manually
  - GIVEN translation ready notification displayed
  - WHEN user presses 'T'
  - THEN translation starts for accumulated content

- AC-4: Threshold increments correctly
  - GIVEN user ignores first threshold (40000)
  - WHEN tokens accumulate to 80000
  - THEN notification updates to "번역 가능 (80000 tokens)"

- AC-5: No notification during active translation
  - GIVEN translation is in progress
  - WHEN new content exceeds next threshold
  - THEN no new notification appears until translation completes

- AC-6: Sequential translation control
  - GIVEN first translation completes
  - WHEN new content exceeds 40000 tokens
  - THEN new notification appears

- AC-7: Exit confirmation with pending content
  - GIVEN user presses 'B' with 20000 untranslated tokens
  - WHEN exit is requested
  - THEN shows "20000 tokens 미번역. 번역 후 종료할까요? (Y/N)"

## Test Strategy

**Unit Tests**:
- FileWatcher threshold notification (no auto-trigger)
- Ready flag management (set/reset)
- Next threshold calculation (40000 → 80000 → 120000)
- Translation state tracking (is_translating)

**Integration Tests**:
- TextPreprocessor menu display with notification
- User input handling ('T' key)
- Full flow: collect → notify → user trigger → translate
- Sequential translations (first complete → second notify)

**CLI Tests**:
- Menu formatting with notification
- Translation status display ("번역 중...")
- Exit confirmation prompt

## Coverage Target

- Line Coverage: 85%
- Branch Coverage: 75%
- Critical paths: 100% (threshold logic, state transitions, user input)

## Performance Criteria

- Notification check: < 1ms (simple flag check)
- No performance regression in collection or translation
- Memory: No additional overhead beyond state variables

## DoD Checklist

- [ ] All 7 acceptance criteria pass
- [ ] Unit tests for FileWatcher extensions
- [ ] Integration tests for CLI menu
- [ ] Manual testing of user flow
- [ ] No auto-translation (verified in tests)
- [ ] Threshold increments work (40k → 80k → 120k)
- [ ] Translation state prevents concurrent translations
- [ ] Exit confirmation tested
- [ ] Documentation updated (README, user guide)
- [ ] Backward compatibility: auto-translation mode still available via config
