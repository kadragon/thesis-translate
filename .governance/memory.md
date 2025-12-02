# Project Memory

- 2025-11-17 (SPEC-CONFIG-001 / TASK-20251117-01): Config now reads all parameters from environment only; missing keys raise ValueError. Added pytest env defaults via `tests/conftest.py` and refreshed translation_config defaults to pick up runtime env. `.env.example` lists required vars.
