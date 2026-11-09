# Backlog

## Review Backlog

### PR #95 — replace OpenAI pipeline with Claude-direct translation workflow (2026-11-08)
- [ ] [debt] Line-end hyphen before a lowercase word is always dropped, so compounds split at a line break (`self-`/`supervised`) lose the hyphen; keep it when the hyphenated form appears elsewhere in the paper or in the term table (source: code-review) — src/core/pdf_extractor.py:169 (introduced here)
- [ ] [debt] Default `glossary.json` is resolved against the CWD and silently skipped when missing, so running `verify` outside the repo root drops the glossary check; resolve it against the project root or warn (source: code-review) — src/main.py:89 (introduced here)

## Telegram bot (design: docs/architecture.md → Telegram Bot)

- [ ] [feat] Result gate: run `verify`; on exit 0 send `<stem>_ko.txt` via `sendDocument`, else send the failure summary
- [ ] [chore] Container image (poppler, uv, claude CLI, kr-style plugin) and deployment steps in `docs/runbook.md`
