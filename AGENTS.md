# AGENTS

## Updates
- 2026-01-08: Tiny last chunk merge now happens in translate via _merge_tiny_last_chunk; chunk_generator no longer merges.
- 2026-01-08: Added model token limits map with env overrides for MODEL_CONTEXT_LENGTH and MODEL_MAX_OUTPUT_TOKENS.
- 2026-01-08: Chunk merge now respects max_token_length; tiny last chunk only merges if combined size is within limit.
- 2026-01-07: Menu prompts accept lowercase inputs via case-insensitive choices.
- 2026-01-07: Translation prompt must output only translated text (no source echo).
- 2026-01-08: SSD-based development process (.spec/.governance/.tasks) retired; key content migrated to AGENTS.md; folders slated for deletion.

## Governance
- TDD required: add a failing test for each behavior change, then implement the minimum code.
- Do not mix structural and behavioral changes in a single commit.
- Run the full test suite (excluding long-running tests) before committing.

## Archived Specs (from .spec/)
- SPEC-REFACTOR-VALIDATION-001: Make progress parameter None-safe with a NoOp handler and document behavior.
- SPEC-REFACTOR-CONSTANTS-001: Extract magic numbers into class constants (timeouts, token ratios, indent).
- SPEC-REFACTOR-COVERAGE-001: Reach 100% coverage for main.py exception path (test or pragma).
- SPEC-REFACTOR-DEDUP-001: Deduplicate sequential/parallel translation paths via shared helpers.
- SPEC-REFACTOR-EXCEPTIONS-001: Merge Transient/Permanent errors into TranslationError(is_transient).
- SPEC-RICH-UX-001: Rich console UX (shared Console + RichHandler, transient progress).
- SPEC-PARALLEL-CHUNKS-001: ThreadPool-based parallel chunk translation (max_workers).
- SPEC-BALANCED-CHUNKS-001: Balanced chunk distribution (pre-scan tokens, target size).
- SPEC-CONFIG-001: Env-backed config and glossary loading with missing-key validation.

## Archived Governance (from .governance/)
- Required env: OPENAI_MODEL, TEMPERATURE, MAX_TOKEN_LENGTH, INPUT_FILE, OUTPUT_FILE, GLOSSARY_FILE, TRANSLATION_MAX_RETRIES, TRANSLATION_RETRY_BACKOFF_SECONDS.
- Coding style: prefer explicit typing/runtime validation for config; keep `Trace: SPEC-ID, TASK-ID` near top of touched modules.
- Patterns: `_require_env` helper with casting; pytest `conftest.py` autouse fixture resets config between tests.
- Learned patterns: NoOp handler, helper extraction for shared logic, prefer is_transient flag over exception hierarchy, entry-point pragma usage.
- Task YAML rules: backlog/current/done split, 2-space indentation, multiline uses `|`.

## Archived Tasks (from .tasks/)
- current_task: null; backlog: empty.
- done (2025-11-17 to 2025-12-28, most recent 10): env-based config, parallel/balanced chunks, Rich UX, constants, 100% coverage, exception unification, progress NoOp, sequential/parallel dedup.
