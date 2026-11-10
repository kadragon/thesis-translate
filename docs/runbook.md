# Runbook

## Setup (local)

- Python 3.12+, [uv](https://docs.astral.sh/uv/), poppler (`brew install poppler` → `pdftotext`)

```bash
uv sync --all-extras
uv run pre-commit install
cp glossary.json.example glossary.json   # optional
```

## Check

| Command | Purpose |
|---------|---------|
| `uv run pytest` | Full suite with coverage (CI runs this) |
| `uv run pytest tests/test_alignment.py -k <name>` | One test |
| `uv run ruff check . && uv run ruff format --check .` | Lint + format check (CI) |
| `uv run mypy .` | Type check (CI) |

CI (`.github/workflows/ci.yml`) runs the four checks above on every PR and push to `main`.

## CLI

```bash
uv run thesis-translate extract paper.pdf --start-page 174 [--first-pdf-page 2] [--force]
uv run thesis-translate verify paper_en.txt paper_ko.txt [--glossary g.json]
uv run thesis-translate format paper_ko.txt
uv run thesis-translate dual paper_en.txt paper_ko.txt
```

Full translation procedure: `.claude/skills/translate-paper/SKILL.md`.

## Telegram Bot

```bash
set -a; source .env; set +a      # TELEGRAM_BOT_TOKEN, TELEGRAM_ALLOWED_CHAT_IDS
uv run thesis-translate-bot      # long polling; Ctrl+C to stop
```

It exits 1 with a Korean message if the token or allowlist is missing. Accepted PDFs land in
`inbox/<stem>.pdf`, wait in an in-memory queue, and run one at a time through `claude -p`
from the directory the bot was started in (start it from the repo root).

### Container (deployment)

```bash
cp .env.example .env        # fill in the three values; stays on the host
claude setup-token          # on a logged-in machine → CLAUDE_CODE_OAUTH_TOKEN
docker compose up -d --build
docker compose logs -f thesis-bot   # job lines: exit code, cost, 거부된 도구 호출 N건
```

`docker-compose.yml` mirrors a plain `docker run --env-file .env --restart unless-stopped`
and deliberately sets no `init` (see below). Every redeploy recreates the container and
discards anything a job wrote, since outputs live only in the container (they reach the
user via Telegram; `docker compose cp thesis-bot:/app/outputs/<stem>/ .` first if needed).

Deployment is manual: run `scripts/deploy.sh` on the server checkout. It refuses to run
off `main`, with local changes, or without `.env`; then pulls `main`, stops the bot
(`docker compose down`, plus the pre-Compose `thesis-bot` container if present — only one
bot may poll a token), rebuilds, and starts it. The bot is down for the whole build. Then
check `docker compose logs --tail=100 thesis-bot` and send the bot a message.

What the image guarantees:

- The bot runs as root (PID 1) and gives each job its own UID (20000 + n, unique within one
  bot process; a restart starts at 20000 again after deleting leftover `/jobs/*` and job-UID
  files in shared tmp dirs) and `/jobs/<id>/{work,home,tmp}` (`src/bot/workspace.py`). The
  workdir links read-only into `/app`; HOME is a copy of the root-owned template `/opt/claude-home/.claude` (settings and
  the `prod@kadragon` plugin for kr-style; the bot exits 1 at startup when it is missing);
  `claude` lives in root-owned `/opt/claude/bin`.
- `/app`, `.venv`, `inbox/`, and `outputs/` are root-owned 0755. After a job, the bot kills
  every process of its UID, deletes that UID's files in `/tmp`, `/var/tmp`, `/dev/shm`,
  copies regular `<stem>_*` files (no symlinks) to root-owned `/app/outputs/<stem>/`, and
  removes `/jobs/<id>` — this is what contains the `Bash(python…)` entries in the allowlist.
- `.env` is never in the image (`.dockerignore`); secrets arrive via `--env-file`, and the
  runner passes only `CHILD_ENV_KEYS` to `claude`.
- The bot is PID 1 (`CMD` runs the venv entry point, no `uv run` parent) and calls
  `prctl(PR_SET_DUMPABLE, 0)` at startup, so no child can read `/proc/1/environ` (the
  token). `docker exec` shells inherit the container env, so do not judge this from an exec
  shell's own `/proc/self/environ`.
- `docker stop` exits cleanly: the bot handles SIGTERM itself (no tini — an init process
  would hold the token in a readable environ) and reaps each job's process group.
- `glossary.json` is bind-mounted from the server checkout (`docker-compose.yml`) so terms
  added over Telegram survive a rebuild; `deploy.sh` creates it as `[]` when missing (a
  missing mount source would become a directory) and sets 0644, so jobs can read but not
  write it. The bot rewrites it in place (same inode); an atomic rename would not reach the
  host file.
- Workdir steering files are neutralized: root-owned `CLAUDE.local.md`, `.python-version`, `UV_NO_CONFIG=1` (ignores `uv.toml`),
  `--strict-mcp-config` (ignores `.mcp.json`), and `verify` runs with `python -P` (a dropped
  `json.py` cannot shadow stdlib).
- Claude Code version is pinned (`CLAUDE_CODE_VERSION` build arg).

Manual check (2026-11-09, Docker 29.8.2, Claude Code 2.1.319): a script run as PID 1 in the
image prepared two jobs through `build_isolation`. As job A's UID, writing to `/app`,
`/app/src`, `/app/outputs`, `/app/inbox`, `/jobs`, `/jobs/<A>`, `/opt/claude-home/.claude`,
`/opt/claude/bin/claude`, `glossary.json`, and job B's `work`/`home`/`tmp` all failed;
`claude --version`, `claude plugin list` (shows `prod`), and `uv run thesis-translate`
worked. A `setsid`'d `sleep`, a `/tmp` file, and an `_en.txt` symlink to `/etc/shadow` left
by job A were gone after sweep/collect/discard: no UID-A process, no `/jobs/<A>`, and
`outputs/a/` held only a root-owned 0644 `a_ko.txt`. Rerun after changing the Dockerfile or
`src/bot/workspace.py`.

Not configured: network egress limits. If the host allows it, restrict outbound traffic to
`api.anthropic.com`, `api.telegram.org`, and the Claude auth endpoints.

Local run without Docker: start from the repo root so the skill finds `glossary.json` and
`<stem>_*.txt` (the model then has your full user rights — prefer the container). Without
root there is no per-job isolation, and unless the bot is PID 1 no stray cleanup between
jobs either: a `setsid`'d leftover of a timed-out job can keep writing in the shared workdir
while the next job runs.

## Environment Variables

| Variable | Required | Purpose |
|----------|----------|---------|
| `TELEGRAM_BOT_TOKEN` | bot | Bot API token from @BotFather |
| `TELEGRAM_ALLOWED_CHAT_IDS` | bot | Comma-separated chat IDs the bot serves; everyone else is ignored |
| `CLAUDE_CODE_OAUTH_TOKEN` | bot (server) | Headless Claude auth from `claude setup-token` |

Template: `.env.example`. Keep real values in `.env` (gitignored, excluded from the image)
or the host's secret store. Find a chat ID by sending
the bot a message and reading `message.chat.id` from `getUpdates`.

## Common Failures

**`텍스트가 없는 쪽이 …` from `extract`** — scanned PDF without a text layer. OCR is out of
scope; tell the user.

**`… 파일이 이미 있습니다` from `extract`** — `<stem>_en.txt` exists and may hold hand cleanup.
Use `--force` only for a deliberate re-extract.

**`PDF 추출 실패`** — `pdftotext` missing or the PDF is encrypted/broken; the message carries
pdftotext's stderr.

**Garbled Korean after a shell edit** — `sed`/`perl` with non-ASCII literals on macOS. Redo the
edit in Python with explicit UTF-8.

**Bot: a translation step silently skipped** — the job log line shows `거부된 도구 호출 N건`
with N > 0: the tool allowlist (`ALLOWED_TOOLS` in `src/bot/runner.py`) blocked it. Add the
narrowest matching entry plus a test.

**Bot: file too large** — Bot API downloads cap at 20 MB, uploads at 50 MB.
