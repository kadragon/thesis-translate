# Backlog

## Review Backlog

### PR #114 — glossary mention check and job snapshot (2026-11-11)

- [ ] [debt] Non-isolated runs (no root) and host-side edits of `glossary.json` still bypass
  `Glossary.lock`, so a dev-mode job's `verify` can read a half-written file (source:
  code-review) — src/bot/glossary.py
