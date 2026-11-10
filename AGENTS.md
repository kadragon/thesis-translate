# AGENTS

## Docs Index (read on demand)

| File | When to read |
|------|--------------|
| `docs/runbook.md` | Setup, test/lint commands, bot deployment, env vars, known failures |
| `docs/architecture.md` | Before touching module boundaries or building the Telegram bot (`src/bot/`) |
| `.claude/skills/translate-paper/SKILL.md` | Translating a paper — the only translation procedure (CLI and bot) |
| `backlog.md` | Queued work and open review findings |

## Golden Principles

1. **No external LLM API.** Claude translates via the translate-paper skill; the bot reaches
   Claude only through the `claude -p` CLI. Enforced: ruff `TID251` bans `openai` and
   `anthropic` imports (`pyproject.toml`).
2. **Bot answers allowlisted chats only.** Updates from a chat ID outside
   `TELEGRAM_ALLOWED_CHAT_IDS` are dropped before any download or job. Enforced:
   `tests/test_bot.py::test_non_allowlisted_chat_gets_no_reply_and_no_download`.
3. **Headless Claude runs with a tool allowlist.** Paper text is untrusted input. Never
   `--dangerously-skip-permissions` or `bypassPermissions`; no web tools in the allowlist.
   Enforced: `tests/test_bot_runner.py` (argv, allowlist, protected-path denies, child env
   allowlist).
4. **Secrets come from the environment only.** `TELEGRAM_BOT_TOKEN`,
   `CLAUDE_CODE_OAUTH_TOKEN` live in `.env` (gitignored) or the host's secret store, never in
   code, logs, or Telegram replies. Enforced: `.gitignore`, `.claude/settings.json` deny.
5. **One source block → one translated block, `p.N` lines untouched.** Enforced:
   `thesis-translate verify` (exit 1 on mismatch); the bot sends `_ko.txt` only after verify
   passes (`tests/test_bot_runner.py::test_failed_verify_sends_no_document`).

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

- 2026-11-10: Allowlisted chats edit `glossary.json` over Telegram: `term → 번역어` lines
  add (existing terms skipped), `/glossary` lists, `/update` changes, `/delete` removes.
  Compose bind-mounts the host's `glossary.json`.
- 2026-11-10: Intake sends one reply with page count and an estimated time; the runner's
  start notice goes only to jobs that waited in the queue.
- 2026-11-10: `getFile`/`sendMessage` use a 30 s socket timeout (was the 10 s long-poll
  slack); `getFile` retries once on `TimeoutError`.
- 2026-11-10: A successful bot job replies with `_ko.txt` plus suggested glossary additions
  only; the step-8 report is skipped.
- 2026-11-10: Bot allowlist adds `Bash(pdfinfo:*)`; the prompt lists the allowed Bash
  prefixes and says a denial is not a reason to stop; each denied call is logged.
