# AGENTS

## Updates
- 2026-01-07: Menu prompts accept lowercase inputs via case-insensitive choices.
- 2026-01-07: Translation prompt must output only translated text (no source echo).
- 2026-01-07: Chunking merges tiny last chunk (<70% of target) into previous even if it exceeds max token length.

## Governance
- TDD required: add a failing test for each behavior change, then implement the minimum code.
- Do not mix structural and behavioral changes in a single commit.
- Run the full test suite (excluding long-running tests) before committing.
