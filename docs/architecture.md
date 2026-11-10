# Architecture

## Source Layout

| Path | Role | May import |
|------|------|-----------|
| `src/core/pdf_extractor.py` | `pdftotext -bbox-layout` → paragraph blocks with `p.N` markers | stdlib |
| `src/core/alignment.py` | Block I/O and `verify` checks (structure, numbers, figure refs, terms) | stdlib |
| `src/utils/` | Output formatting, Rich logging | stdlib, `rich` |
| `src/main.py` | `thesis-translate extract\|verify\|format\|dual` CLI | `core`, `utils` |
| `src/bot/` | Telegram bot: `config` (env), `telegram_api` (urllib client), `handler` (allowlist, PDF/size checks), `intake` (download, stem), `jobs` (queue), `main` (poll loop, wiring) | `core`, `utils`, stdlib `subprocess` |

Dependency direction: `bot` → `main`/`core`/`utils`. `core` never imports `bot` or `main`.

## Translation Is a Skill, Not Code

The translation step (term table, block-by-block translation, accuracy review, kr-style
polish) is a procedure in `.claude/skills/translate-paper/SKILL.md` that Claude Code executes.
Python code only prepares input (`extract`) and checks output (`verify`, `format`, `dual`).
Any new entry point — including the bot — drives that skill; it does not reimplement it.

## Telegram Bot — decided constraints

Decided on 2026-11-09: headless `claude -p`, runs on a separate server/container, allowlisted
chat IDs only.

```
Telegram ──long poll──▶ src/bot (receive, allowlist, queue)
                           │ one job at a time
                           ▼
                  inbox/<job>.pdf  (gitignored)
                           │ subprocess, cwd = repo root
                           ▼
          claude -p "<translate-paper request>" --allowedTools …
                           │ runs extract → … → verify → format
                           ▼
          <stem>_ko.txt (+ _dual.txt) ──sendDocument──▶ same chat
```

- **Transport**: long polling (`getUpdates`); no public endpoint or webhook needed.
  `poll_once` advances the offset before handling each update and logs per-update
  errors, so a failing update is never replayed (a replay would queue the PDF again).
- **Access**: drop any update whose chat ID is not in `TELEGRAM_ALLOWED_CHAT_IDS` before
  downloading anything (golden principle 2).
- **Input**: accept `application/pdf` documents only. Bot API downloads cap at 20 MB; reply
  with a Korean error above that instead of failing silently.
- **Queue**: one translation at a time; a paper takes minutes to hours on one subscription.
  The skill's file contract (`<stem>_*.txt`, `glossary.json`) resolves against the CWD: the
  job's own workdir in root mode, the repo root otherwise. Acknowledge receipt and queue position immediately.
- **Claude invocation** (`src/bot/runner.py`): `build_claude_argv()` is the single argv
  source — `claude -p --output-format json --permission-mode dontAsk
  --no-session-persistence --allowedTools … --disallowedTools WebFetch WebSearch`; the prompt
  goes in on stdin (the variadic tool flags would swallow a positional prompt). `dontAsk`
  denies anything off the list. `ALLOWED_TOOLS` includes `Bash(uv run python:*)` and
  `Bash(python3:*)` for the skill's UTF-8 edits and the kr-style audit — arbitrary code,
  acceptable only inside the container. `DISALLOWED_TOOLS` also denies Edit/Write on
  `PROTECTED_PATHS` (code, tests, harness, `glossary.json`, `.env`) and `Read(./.env)`;
  deny beats allow. The child env is the `CHILD_ENV_KEYS` allowlist (no `TELEGRAM_*`).
  Also `--strict-mcp-config`; `verify` runs as `python -P`. The bot process is
  non-dumpable (`disable_dumpable`, `prctl`) so no child can read its environ. Python can
  bypass path denies; per-job isolation (below) is what contains it.
  Claude runs via `run_in_group` (new session); its whole process group is killed and
  reaped after it exits or times out. Hostile code can `setsid` out of the group, so as
  PID 1 (container) the runner also SIGKILLs every other process of its UID
  (`kill_same_uid_strays`) before verify and upload. Every text
  sent to Telegram goes through `ClaudeRunner._redact` (`SECRET_ENV_KEYS` values and
  `sk-ant-…` tokens). Notifier failures are logged; a failed upload falls back to a text
  message naming the server-side file.
  Timeout 4 h. The log line counts `permission_denials` and logs each one (`Tool: command`,
  redacted, clipped): a non-zero count means the allowlist blocked a step. The prompt lists the
  allowed Bash prefixes and tells the model to rephrase a denied command rather than stop —
  without it, one denied `P=…; pdfinfo …` made a run abandon the job before `extract`.
- **Isolation (root mode, `src/bot/workspace.py`)**: when the bot runs as root,
  `build_isolation` gives each job a never-reused UID (from 20000) and
  `/jobs/<id>/{work,home,tmp}`: `work` holds symlinks to the read-only checkout entries the
  skill needs plus a copy of the PDF; `home` is seeded from `/opt/claude-home/.claude`. Claude
  and `verify` run as that UID (`extra_groups=[]`). After Claude exits the UID is swept, the
  four `<stem>_*` outputs are copied (regular files only, `O_NOFOLLOW` via a dir fd) into
  root-owned `outputs/<stem>/`, `verify` runs there, and `/jobs/<id>` plus the UID's files in
  `/tmp`, `/var/tmp`, `/dev/shm` are deleted. Non-root runs keep the shared-CWD mode below and
  warn at startup. The `Dockerfile` runs the bot as root, so the container always uses root
  mode. Design: `docs/design/per-job-isolation.md`; image guarantees and the manual check:
  `docs/runbook.md`.
- **Stem**: `sanitize_stem` keeps the base name only, maps unsafe characters to `_`, strips
  leading `-`/`.` (no CLI flags), caps 120 chars. If `<stem>` is queued/running or
  `inbox/<stem>.pdf`, `<stem>_en.txt`, `<stem>_ko.txt` exists, append `_<job_id>` instead of
  `--force`.
- **Content check**: after download the file must carry `%PDF-` in its first 1024 bytes;
  otherwise it is deleted and the user told.
- **Result gate** (`ClaudeRunner._deliver`): after Claude exits 0, require `<stem>_ko.txt`,
  run `python -m src.main verify` in the workdir, and only on exit 0 upload it with
  `sendDocument` (multipart, 50 MB cap), then send the `term → 번역어` lines of Claude's final
  message as glossary suggestions (the prompt skips the step-8 report), nothing when there are none. Any failure sends a
  Korean reason and no document (golden principle 5).
- **Scans**: `extract` refuses image-only PDFs; relay that message — OCR is out of scope.

Client library: none — `src/bot/telegram_api.py` calls the Bot API with stdlib `urllib`
(no new dependency; the bot needs only `getUpdates`, `sendMessage`, file download/upload).
The allowlist must not be empty: `load_config` refuses to start otherwise.

The queue is in memory: a restart drops queued jobs (the PDFs stay in `inbox/`).

Open: job persistence across restarts, whether `_dual.txt` is sent by default.
