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
docker build -t thesis-translate-bot .
docker run -d --name thesis-bot --restart unless-stopped --env-file .env thesis-translate-bot
docker logs -f thesis-bot   # job lines: exit code, cost, 거부된 도구 호출 N건
```

Update: `git pull`, rebuild, `docker rm -f thesis-bot`, run again. A rebuild also discards
anything a job wrote, since outputs live only in the container (they reach the user via
Telegram; `docker cp thesis-bot:/app/<stem>_ko.txt .` before removing it if needed).

What the image guarantees (verified with `docker run … bash`):

- Runs as uid `bot`. `/app` and `.venv` are root-owned and read-only for `bot`; `/app` has
  the sticky bit, so jobs can create `<stem>_*` files and `inbox/` but cannot modify, rename,
  or delete code, the harness, or `glossary.json` — this is what contains the
  `Bash(python…)` entries in the tool allowlist.
- `.env` is never in the image (`.dockerignore`); secrets arrive via `--env-file`, and the
  runner passes only `CHILD_ENV_KEYS` to `claude`.
- The bot is PID 1 (`CMD` runs the venv entry point, no `uv run` parent) and calls
  `prctl(PR_SET_DUMPABLE, 0)` at startup, so the same-UID `claude` child cannot read
  `/proc/1/environ` (the token). `docker exec` shells inherit the container env, so do not
  judge this from an exec shell's own `/proc/self/environ`.
- `docker stop` exits cleanly: the bot handles SIGTERM itself (no tini — an init process
  would hold the token in a readable environ) and reaps each job's process group.
- Workdir steering files are neutralized: root-owned `CLAUDE.local.md`, `.python-version`,
  and `glossary.json` (`[]` when the host has none), `UV_NO_CONFIG=1` (ignores `uv.toml`), `--strict-mcp-config` (ignores
  `.mcp.json`), and `verify` runs with `python -P` (a dropped `json.py` cannot shadow stdlib).

Residual risk (backlog): jobs share `/app` and `/home/bot`, so a PDF that escapes through
Python could alter later jobs' outputs or `~/.claude` until the container is recreated.
- Claude Code version is pinned (`CLAUDE_CODE_VERSION` build arg); the `prod@kadragon`
  plugin (kr-style) is installed for `bot`.

Not configured: network egress limits. If the host allows it, restrict outbound traffic to
`api.anthropic.com`, `api.telegram.org`, and the Claude auth endpoints.

Local run without Docker: start from the repo root so the skill finds `glossary.json` and
`<stem>_*.txt` (the model then has your full user rights — prefer the container).

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

**`verify` skips the glossary outside the repo root** — `glossary.json` resolves against CWD
(backlog debt item). Run from the repo root.

**Garbled Korean after a shell edit** — `sed`/`perl` with non-ASCII literals on macOS. Redo the
edit in Python with explicit UTF-8.

**Bot: a translation step silently skipped** — the job log line shows `거부된 도구 호출 N건`
with N > 0: the tool allowlist (`ALLOWED_TOOLS` in `src/bot/runner.py`) blocked it. Add the
narrowest matching entry plus a test.

**Bot: file too large** — Bot API downloads cap at 20 MB, uploads at 50 MB.
