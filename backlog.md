# Backlog


## Review Backlog

### PR #113 — edit glossary.json from Telegram (2026-11-10)

- [ ] [debt] Glossary commands accept any `/cmd@name` suffix; in a group with another bot,
  `/delete@other_bot term` still runs here — check the mention against `getMe` (source:
  code-review) — src/bot/glossary.py:33
- [ ] [debt] In-place glossary rewrite has a truncate-then-write window in which a running
  job's `verify` could read a partial file; consider a directory mount with
  rename-based writes (source: code-review) — src/bot/glossary.py:101
