# Telegram translation bot: thesis-translate-bot + headless Claude Code.
# Build:  docker build -t thesis-translate-bot .
# Run:    see docs/runbook.md (Telegram Bot → Container).
#
# The bot runs as root (PID 1) and gives every job its own throwaway UID and
# /jobs/<id>/{work,home,tmp} (src/bot/workspace.py). Everything a job reads from
# the image is root-owned and not writable by it.
FROM python:3.12-slim

ARG CLAUDE_CODE_VERSION=2.1.319
ARG PLUGIN_MARKETPLACE=kadragon/agent-toolkit

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_NO_SYNC=1 \
    UV_FROZEN=1 \
    UV_NO_CONFIG=1 \
    PATH=/opt/claude/bin:$PATH

RUN apt-get update \
 && apt-get install -y --no-install-recommends poppler-utils ca-certificates curl git \
 && rm -rf /var/lib/apt/lists/*
COPY --from=ghcr.io/astral-sh/uv:0.13.1 /uv /usr/local/bin/uv

# Claude Code in a root-owned, world-executable location, plus a root-owned
# ~/.claude template with the kr-style plugin (translate-paper step 7). Each job
# gets a copy of the template's .claude as its own HOME. The template path is
# fixed: src/bot/main.py reads it as HOME_TEMPLATE.
RUN mkdir -p /opt/claude/bin /opt/claude-home \
 && curl -fsSL https://claude.ai/install.sh \
    | HOME=/opt/claude-home bash -s "${CLAUDE_CODE_VERSION}" \
 && install -m 0755 "$(readlink -f "/opt/claude-home/.local/bin/claude")" /opt/claude/bin/claude \
 && rm -rf "/opt/claude-home/.local" \
 && HOME=/opt/claude-home claude plugin marketplace add "${PLUGIN_MARKETPLACE}" \
 && HOME=/opt/claude-home claude plugin install prod@kadragon \
 && chown -R root:root /opt/claude /opt/claude-home \
 && chmod -R go-w,a+rX /opt/claude /opt/claude-home

# The checkout is root-owned and read-only for jobs: they work in /jobs/<id>/work
# through symlinks into /app, and the bot copies their outputs to
# /app/outputs/<stem>/ once the job UID has no process left.
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project
COPY . .
# Root-owned placeholders: files claude/uv would read from the workdir.
RUN uv sync --frozen \
 && touch CLAUDE.local.md && echo 3.12 > .python-version \
 && { [ -f glossary.json ] || echo '[]' > glossary.json; } \
 && mkdir -p inbox outputs /jobs \
 && chmod 0755 /app inbox outputs /jobs

# Exec the venv entry point directly: a `uv run` parent would stay alive holding
# the bot token in its own (dumpable) environ.
CMD ["/app/.venv/bin/thesis-translate-bot"]
