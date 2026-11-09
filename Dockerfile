# Telegram translation bot: thesis-translate-bot + headless Claude Code.
# Build:  docker build -t thesis-translate-bot .
# Run:    see docs/runbook.md (Telegram Bot → Container).
FROM python:3.12-slim

ARG CLAUDE_CODE_VERSION=2.1.319
ARG PLUGIN_MARKETPLACE=kadragon/agent-toolkit

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_NO_SYNC=1 \
    UV_FROZEN=1 \
    UV_NO_CONFIG=1 \
    PATH=/home/bot/.local/bin:$PATH

RUN apt-get update \
 && apt-get install -y --no-install-recommends poppler-utils ca-certificates curl git \
 && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:0.13.1 /uv /usr/local/bin/uv

RUN useradd --create-home --uid 10001 bot

# Claude Code and the kr-style plugin (translate-paper step 7) for the bot user.
USER bot
RUN curl -fsSL https://claude.ai/install.sh | bash -s "${CLAUDE_CODE_VERSION}" \
 && claude plugin marketplace add "${PLUGIN_MARKETPLACE}" \
 && claude plugin install prod@kadragon

# The checkout is root-owned and read-only for the bot. /app is world-writable
# with the sticky bit so jobs can add <stem>_* files and inbox/ but cannot
# modify, rename, or delete code, the harness, or glossary.json.
USER root
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project
COPY . .
# Root-owned placeholders: files claude/uv would read from the workdir must not
# be creatable by one job to steer the next.
RUN uv sync --frozen \
 && touch CLAUDE.local.md && echo 3.12 > .python-version \
 && { [ -f glossary.json ] || echo '[]' > glossary.json; } \
 && chmod 1777 /app

USER bot
ENV UV_CACHE_DIR=/home/bot/.cache/uv
# Exec the venv entry point directly: a `uv run` parent would stay alive holding
# the bot token in its own (dumpable) environ.
CMD ["/app/.venv/bin/thesis-translate-bot"]
