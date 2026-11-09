# Per-Job Isolation for the Telegram Bot

## Problem Statement
Every translation job runs `claude -p` as the same UID (`bot`, 10001) in the same
container, with `/app` (mode 1777) as its CWD and `/home/bot` as its HOME. The tool
allowlist includes `Bash(python3:*)` and `Bash(uv run python:*)`, so a prompt-injected PDF
can run arbitrary code. The PID-1 UID sweep (`kill_same_uid_strays`) stops leftover
processes, but files the job already wrote stay behind: it can plant or alter `<stem>_*`
files of later jobs, or rewrite `~/.claude` (settings, plugins, skills) and steer every
later job until the container is recreated. Source: backlog PR #99 `[security]` item.

## Solution
Give each job its own throwaway UID and directories inside the existing container. The bot
runs as root (PID 1). It creates `/jobs/<job_id>/{work,home,tmp}`, seeds them, and runs
`claude` (and `verify`) as a fresh, never-before-used UID. Then it kills every process of
that UID, sweeps that UID's files from shared writable dirs, copies the outputs into a
root-owned `/app/outputs/<stem>/`, and deletes `/jobs/<job_id>`. Jobs cannot write to
`/app`, to the outputs, or to any other job's HOME.

## User Stories
- As the bot operator, I want a hostile PDF to be unable to affect any later job, so that
  one bad upload does not force a container rebuild to restore trust.
- As the bot operator, I want finished translations kept on the server, so that I can still
  `docker cp` a result (e.g. one over Telegram's 50 MB upload cap).
- As a developer, I want `uv run thesis-translate-bot` to keep working on my laptop without
  root, so that local testing stays simple.

## Implementation Decisions
- **Privilege model (user decision, 2026-11-09):** bot process runs as root in the
  container; each job drops to its own UID via `subprocess.Popen(user=, group=,
  extra_groups=[])`. Verified in `python:3.12-slim`: root can switch to an arbitrary UID with
  Docker's default capabilities; non-root `bot` cannot; `unshare(CLONE_NEWUSER)` is denied
  for both under Docker's default seccomp.
- **UID allocation:** `20000 + n`, where `n` increases with every job in this process and is
  never reused within the process lifetime. On startup the bot deletes any leftover
  `/jobs/*` (a restart restarts `n`, so stale state of a reused UID must be gone first).
  The GID equals the UID; no supplementary groups.
- **Workdir (`/jobs/<id>/work`, owned by the job UID):** symlinks to the root-owned,
  read-only `/app` entries the skill and CLI need — `.claude`, `src`, `pyproject.toml`,
  `uv.lock`, `.venv`, `glossary.json`, `AGENTS.md`, `CLAUDE.md`, `CLAUDE.local.md`,
  `.python-version` — plus a copy of the job's PDF. Verified locally: `UV_NO_SYNC=1 uv run
  thesis-translate` works from such a directory and `src.main.PROJECT_ROOT` resolves to the
  real checkout. `PROTECTED_PATHS` denies keep applying (paths are relative to CWD), and
  writes through a symlink fail on the root-owned target anyway.
- **HOME (`/jobs/<id>/home`):** seeded by copying a root-owned template of `~/.claude`
  (settings + the `prod@kadragon` plugin) built into the image, then chowned to the job UID.
  The `claude` binary moves to a root-owned, world-executable location (e.g. `/opt/claude`)
  on `PATH`, so it no longer lives in a writable HOME. `TMPDIR`, `XDG_CACHE_HOME`,
  `XDG_CONFIG_HOME` point inside `/jobs/<id>/`; `UV_CACHE_DIR` points to the per-job tmp.
- **Child env:** still the `CHILD_ENV_KEYS` allowlist; `HOME`, `USER`, `TMPDIR`, `XDG_*`
  are overridden per job rather than inherited from the bot.
- **After Claude exits (or times out):** kill the process group, then SIGKILL every process
  of the job UID (`kill_same_uid_strays(uid=job_uid)` — no longer limited to PID 1, since a
  per-job UID is safe to sweep anywhere), then remove files owned by that UID in `/tmp`,
  `/var/tmp`, `/dev/shm`.
- **Output copy-out (user decision, 2026-11-09 — keep outputs):** with no job process left,
  the bot copies `<stem>_en.txt`, `_ko.txt`, `_terms.json`, `_review.md` from the workdir
  into root-owned `/app/outputs/<stem>/` (mode 0644, dir 0755). Each source is opened with
  `O_NOFOLLOW` and must be a regular file under `MAX_UPLOAD_BYTES`-scale limits; anything
  else is skipped and logged. Then `/jobs/<id>` is removed (`shutil.rmtree`, symlink-safe).
- **Verify gate:** `python -P -m src.main verify` runs as the job UID with CWD
  `/app/outputs/<stem>/` on the copied files (readable, not writable by it); on exit 0 the
  bot uploads the copied `_ko.txt`. Golden principle 5 is unchanged.
- **Image:** `/app` becomes root-owned 0755 (no more 1777); `/app/inbox` and `/app/outputs`
  are root-owned. `USER bot` is dropped from the final stage; `CMD` still execs the venv
  entry point as PID 1, and `prctl(PR_SET_DUMPABLE, 0)` stays.
- **Intake:** the stem-collision check reads `/app/outputs/<stem>/` instead of `<stem>_*`
  in the workdir.
- **Non-root runs (local dev):** when `os.geteuid() != 0`, the bot keeps today's shared-CWD
  behavior and logs a Korean warning at startup that jobs are not isolated.

## Alternatives rejected
- Privilege-separated launcher (root PID 1 that only spawns jobs, bot logic as `bot` over
  IPC) — safest, but adds a second process and an IPC protocol; the bot's input surface
  (allowlisted chats only) does not justify it now.
- One throwaway container per job — needs the Docker socket inside the bot container,
  which is root on the host.
- bubblewrap / user namespaces inside the container — `unshare(CLONE_NEWUSER)` is denied
  under Docker's default seccomp (verified), and loosening seccomp widens the whole container.
- Copying the checkout into each job workdir instead of symlinking — slower and duplicates
  `.venv`; symlinks to root-owned targets give the same read-only view.

## Testing Decisions
- Unit tests (`tests/test_bot_runner.py`, new `tests/test_bot_workspace.py` if a module is
  split out), with injected `run`/filesystem hooks: each job gets a distinct UID passed as
  `user`/`group`/`extra_groups=[]`; child env `HOME`/`TMPDIR` point under `/jobs/<id>/`;
  copy-out rejects symlinks and non-regular files; the job directory is removed on success,
  failure, and timeout; verify runs as the job UID on the copied files; non-root mode keeps
  the current argv/cwd.
- Existing guarantees stay green: allowlist/argv, protected-path denies, child-env
  allowlist, `test_failed_verify_sends_no_document`.
- Command: `uv run pytest && uv run ruff check . && uv run mypy src`.
- Manual Docker check, recorded in `docs/runbook.md` → "What the image guarantees": as a job
  UID, writing to `/app`, `/app/outputs`, the HOME template, or another job's dir fails;
  after a job, `/jobs/<id>` is gone and no process of that UID remains.

## Out of Scope
- Network egress limits (still "Not configured" in the runbook).
- Job persistence across restarts and parallel jobs (the queue stays single-worker).
- Pruning or rotating `/app/outputs`.
- Hardening the bot's own Telegram handling beyond what it does today.

## Further Notes
- Running the bot as root raises the cost of any bug in `src/bot/` intake/handler code;
  revisit the privilege-separated launcher if the bot ever accepts non-allowlisted input.
- `/app/outputs` lives in the container only; the runbook's `docker cp` path changes to
  `/app/outputs/<stem>/`.
- Update `docs/architecture.md` (Queue, Claude invocation, residual risk) and remove the
  runbook's "Residual risk (backlog)" line when this lands.
