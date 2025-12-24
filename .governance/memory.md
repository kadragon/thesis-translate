# Project Memory

## Recent Changes

- 2025-12-24 (SPEC-BALANCED-CHUNKS-001 / TASK-20251224-01): Implemented balanced chunk distribution algorithm to improve parallel translation efficiency. Previously, greedy chunking created unbalanced chunks (e.g., 19,592 vs 8,115 tokens), causing the largest chunk to bottleneck parallel processing. New 3-phase algorithm: (1) pre-scan total tokens, (2) calculate num_chunks and target_chunk_size, (3) distribute lines evenly at line boundaries. Result: ~20% reduction in parallel translation time by ensuring all worker threads complete at similar times. All 54 tests pass with 99% coverage. Updated `src/core/streaming_translator.py::chunk_generator` and added 4 new balanced distribution tests.

- 2025-12-07 (SPEC-PARALLEL-CHUNKS-001 / TASK-20251207-02): Added a safe default `OPENAI_API_KEY` in `tests/conftest.py` using `setdefault` so OpenAI client instantiation during tests no longer fails when the env lacks a key. This does not override real secrets. All tests now pass via `uv run pytest`.

- 2025-12-07 (SPEC-PARALLEL-CHUNKS-001 / TASK-20251207-01): Implemented parallel chunk translation using ThreadPoolExecutor. Chunks are now processed concurrently (max_workers=3 by default) to reduce total translation time. Added `TRANSLATION_MAX_WORKERS` config (clamped 1-10). Removed file monitoring and user-prompted translation features (concurrent-translation, user-prompted-translation specs and implementations deleted). Sequential mode (max_workers=1) maintained for backward compatibility. All tests pass.

- 2025-12-02: Migrated task tracking from Markdown to YAML format per CLAUDE.md standards. Created `backlog.yaml`, `current.yaml`, and `done.yaml` with proper indentation structure to prevent parsing errors. Migrated 5 completed tasks from legacy `.md` files. This ensures compliance with SDD×TDD governance requirements and prevents YAML indentation errors identified in code review.

- 2025-11-17 (SPEC-CONFIG-001 / TASK-20251117-01): Config now reads all parameters from environment only; missing keys raise ValueError. Added pytest env defaults via `tests/conftest.py` and refreshed translation_config defaults to pick up runtime env. `.env.example` lists required vars.

## Task Management

### Format Standards
- **backlog.yaml**: Pending tasks in priority order under `pending_tasks:` list
- **current.yaml**: Single active task under `current_task:` (null when none active)
- **done.yaml**: Completed tasks under `completed_tasks:` list with 2-space indentation

### Critical YAML Rules
1. List items must use 2-space indentation under parent key
2. Properties use 4-space indentation
3. Never place list items (`- task_id:`) at root level
4. Multi-line strings use `|` indicator with proper indentation

### Migration Notes
- Legacy `.md` files preserved until confirmed unnecessary
- All 5 historical tasks successfully migrated to `done.yaml`
- YAML validation passes for all three files
