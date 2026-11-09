# Backlog

## Review Backlog

### PR #103 — bot job hardening (2026-11-09)
- [ ] [doc] Non-root mode no longer blocks after a job timeout, so a `setsid`'d leftover of a timed-out job can keep writing in the shared workdir while the next job runs (`_sweep_strays` only acts as PID 1); state in the runbook and startup warning that non-root mode does no stray cleanup between jobs (source: code-review) — src/bot/runner.py:205, src/bot/main.py:70
