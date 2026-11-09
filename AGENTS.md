# AGENTS

## Docs Index (read on demand)

| File | When to read |
|------|--------------|
| `docs/runbook.md` | Setup, test/lint commands, bot deployment, env vars, known failures |
| `docs/architecture.md` | Before touching module boundaries or building the Telegram bot (`src/bot/`) |
| `.claude/skills/translate-paper/SKILL.md` | Translating a paper — the only translation procedure (CLI and bot) |
| `backlog.md` | Queued work, including the Telegram bot slices |

## Golden Principles

1. **No external LLM API.** Claude translates via the translate-paper skill; the bot reaches
   Claude only through the `claude -p` CLI. Enforced: ruff `TID251` bans `openai` and
   `anthropic` imports (`pyproject.toml`).
2. **Bot answers allowlisted chats only.** Updates from a chat ID outside
   `TELEGRAM_ALLOWED_CHAT_IDS` are dropped before any download or job. Enforced:
   `tests/test_bot.py::test_non_allowlisted_chat_gets_no_reply_and_no_download`.
3. **Headless Claude runs with a tool allowlist.** Paper text is untrusted input. Never
   `--dangerously-skip-permissions` or `bypassPermissions`; no web tools in the allowlist.
   Enforced: `tests/test_bot_runner.py` (argv, allowlist, child env without `TELEGRAM_*`).
4. **Secrets come from the environment only.** `TELEGRAM_BOT_TOKEN`,
   `CLAUDE_CODE_OAUTH_TOKEN` live in `.env` (gitignored) or the host's secret store, never in
   code, logs, or Telegram replies. Enforced: `.gitignore`, `.claude/settings.json` deny.
5. **One source block → one translated block, `p.N` lines untouched.** Enforced:
   `thesis-translate verify` (exit 1 on mismatch); the bot must not deliver a failing result.

## Working with Existing Code

- `src/core/` is pure (no I/O beyond the files it is handed, no Telegram, no subprocess to
  `claude`). The bot lives in `src/bot/` and calls the CLI/skill, never the reverse.
- Paper outputs (`*.txt`, `*_terms.json`, `*_review.md`) sit in the repo root and are
  gitignored (`*.txt`); do not commit them or clean them up unasked.
- Bulk edits on Korean text: Python with explicit UTF-8, never `sed`/`perl` with non-ASCII
  literals (they corrupt bytes on macOS).
- `extract` refuses to overwrite an existing `_en.txt` (hand cleanup lives there); `--force`
  only on a deliberate re-extract.

## Governance

- TDD required: add a failing test for each behavior change, then implement the minimum code.
- Do not mix structural and behavioral changes in a single commit.
- Run the full suite before committing (`uv run pytest`; pre-commit runs ruff, mypy, pytest).

## Language Policy

- Code, comments, commits, `docs/`, `AGENTS.md`, skills: English.
- CLI log messages, bot replies, `README.md`: Korean (existing convention).

## Maintenance

Edit this file only for stable, non-inferable guidance whose absence causes mistakes; prefer
fixing stale lines over appending, and move detail into `docs/`. Durable repo facts go here or
in `docs/`; personal preferences stay in auto-memory. Log notable behavior changes under
Updates (newest first, keep ~5).

## Updates

- 2026-11-09: Bot job runner `src/bot/runner.py`: `claude -p --permission-mode dontAsk` with a
  tool allowlist, prompt on stdin, 4 h timeout, failures reported to the chat.
- 2026-11-09: Bot intake: PDF download to `inbox/` (non-PDF, >20 MB, bad header rejected),
  sanitized `<stem>` with job-ID suffix on collision, in-memory single-worker `JobQueue`.
- 2026-11-09: Bot skeleton `thesis-translate-bot` (`src/bot/`): stdlib long polling,
  allowlist gate, Korean receipt for PDFs; refuses to start without token/allowlist.
- 2026-11-09: Harness set up for the Telegram bot (`docs/`, golden principles, ruff ban on LLM
  SDKs, `.claude/settings.json` deny rules). OpenAI-era archive sections removed.
- 2026-11-08: `verify` also warns on missing source numbers, `Figure/Table N` without
  `그림/표 N`, and term-table violations; `extract` refuses scans; new `dual` command.
- 2026-11-08: `extract` splits paragraphs by `pdftotext -bbox-layout` line geometry;
  `verify` warns when a translation is under 0.3x its source length.
- 2026-11-08: OpenAI translation pipeline removed; CLI is `thesis-translate
  extract|verify|format|dual`.
