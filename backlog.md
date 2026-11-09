# Backlog

## Review Backlog

### PR #99 — Telegram bot (2026-11-09)
- [ ] [security] Jobs share `/app` and `/home/bot` as one UID, so a prompt-injected job that runs Python can tamper with later jobs' outputs or `~/.claude` until the container is recreated (the PID-1 UID sweep stops leftover processes, not
  files already written); run each job in a per-job workdir under a separate UID or a throwaway container (source: security-review) — src/bot/runner.py, Dockerfile


