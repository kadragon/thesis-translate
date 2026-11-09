# Backlog

## 2 — per-job isolation image
- [ ] [FEAT] Switch the image to root-mode isolation: bot runs as root (PID 1), `claude` binary in root-owned `/opt/claude`, root-owned `~/.claude` HOME template with the prod plugin, `/app` 0755 with root-owned `inbox/` and `outputs/`; update runbook (image guarantees, docker cp path, drop residual-risk line) and architecture
  Source: docs/design/per-job-isolation.md → Implementation Decisions (Image, HOME), Testing Decisions (manual Docker check)
  Done when: in the built image, a job UID cannot write `/app`, `/app/outputs`, the HOME template, or another job's dir; after a test job `/jobs/<id>` is gone and no process of that UID remains (recorded in docs/runbook.md) → `docker build` + the manual check, plus `uv run pytest`
  Approach: Dockerfile only plus docs; no runner logic changes beyond wiring the template path

## Review Backlog

### PR #99 — Telegram bot (2026-11-09)
- [ ] [security] Jobs share `/app` and `/home/bot` as one UID, so a prompt-injected job that runs Python can tamper with later jobs' outputs or `~/.claude` until the container is recreated (the PID-1 UID sweep stops leftover processes, not *(blocked by: 2-per-job-isolation-image)*
  files already written); run each job in a per-job workdir under a separate UID or a throwaway container (source: security-review) — src/bot/runner.py, Dockerfile

### feat/per-job-isolation-runner — implementation finding (2026-11-09)
- [ ] [debt] `run_in_group` blocks after a timeout until any `setsid`'d descendant that still holds the stdout/stderr pipe exits, so a hostile job can stall the single worker indefinitely; sweep the job UID (or close the pipes) before the second `communicate()` (source: container check during implementation) — src/bot/runner.py:195
