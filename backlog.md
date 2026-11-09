# Backlog

## Review Backlog

### PR #99 — Telegram bot (2026-11-09)
- [ ] [security] Jobs share `/app` and `/home/bot` as one UID, so a prompt-injected job that runs Python can tamper with later jobs' outputs or `~/.claude` until the container is recreated (the PID-1 UID sweep stops leftover processes, not
  files already written); run each job in a per-job workdir under a separate UID or a throwaway container (source: security-review) — src/bot/runner.py, Dockerfile


### PR #95 — replace OpenAI pipeline with Claude-direct translation workflow (2026-11-08)
- [ ] [debt] Line-end hyphen before a lowercase word is always dropped, so compounds split at a line break (`self-`/`supervised`) lose the hyphen; keep it when the hyphenated form appears elsewhere in the paper or in the term table (source: code-review) — src/core/pdf_extractor.py:169 (introduced here)
- [ ] [debt] Default `glossary.json` is resolved against the CWD and silently skipped when missing, so running `verify` outside the repo root drops the glossary check; resolve it against the project root or warn (source: code-review) — src/main.py:89 (introduced here)
