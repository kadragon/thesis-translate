# Backlog

## Review Backlog

### feat/per-job-isolation-runner — implementation finding (2026-11-09)
- [ ] [debt] `run_in_group` blocks after a timeout until any `setsid`'d descendant that still holds the stdout/stderr pipe exits, so a hostile job can stall the single worker indefinitely; sweep the job UID (or close the pipes) before the second `communicate()` (source: container check during implementation) — src/bot/runner.py:195

### PR #102 — per-job isolation image (2026-11-09)
- [ ] [debt] `Isolation._populate` skips the HOME template silently when `/opt/claude-home/.claude` is missing, so a broken image runs every job without the prod plugin (no kr-style step); fail `build_isolation` at startup instead (source: code-review) — src/bot/workspace.py:126, src/bot/main.py:36
