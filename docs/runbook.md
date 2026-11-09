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
`inbox/<stem>.pdf` and wait in an in-memory queue; until the job-runner slice lands, each job
only gets a "실행기가 아직 연결되지 않았습니다" reply when its turn comes.

Server/container requirements (deployment steps land with the container slice):

- `pdftotext` (poppler-utils), `uv`, Python 3.12, and the `claude` CLI on `PATH`.
- Claude auth for headless runs: run `claude setup-token` on a logged-in machine and set the
  printed token as `CLAUDE_CODE_OAUTH_TOKEN` on the server.
- The translate-paper skill comes with the repo checkout, but its kr-style step invokes
  `prod:kr-style` from a user plugin. Install that plugin on the server, or the step is
  skipped — check the bot's job log for it.
- Run from the repo root (the skill resolves `glossary.json` and `<stem>_*.txt` against CWD).

## Environment Variables

| Variable | Required | Purpose |
|----------|----------|---------|
| `TELEGRAM_BOT_TOKEN` | bot | Bot API token from @BotFather |
| `TELEGRAM_ALLOWED_CHAT_IDS` | bot | Comma-separated chat IDs the bot serves; everyone else is ignored |
| `CLAUDE_CODE_OAUTH_TOKEN` | bot (server) | Headless Claude auth from `claude setup-token` |

Keep real values in `.env` (gitignored) or the host's secret store. Find a chat ID by sending
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

**Bot: file too large** — Bot API downloads cap at 20 MB, uploads at 50 MB.
