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

- 2026-11-10: Bot allowlist adds `Bash(pdfinfo:*)`; the prompt lists the allowed Bash
  prefixes and says a denial is not a reason to stop; each denied call is logged.
- 2026-11-09: In root mode the bot refuses to start without `/opt/claude-home/.claude`;
  a job timeout no longer waits on `setsid`'d descendants holding the output pipes.
- 2026-11-09: The image runs the bot as root, so every container job is isolated; `claude`
  lives in `/opt/claude/bin`, the HOME template in `/opt/claude-home`, outputs in
  `/app/outputs/<stem>/` (runbook has the manual check).
- 2026-11-09: Bot runner has a root mode (`src/bot/workspace.py`): per-job UID and
  `/jobs/<id>` workspace, outputs copied to root-owned `outputs/<stem>/`.
- 2026-11-09: `extract` keeps a line-end hyphen when the compound appears whole elsewhere in
  the paper or in `glossary.json`; `verify`/`extract` read `glossary.json` from the project
  root, not the CWD.
