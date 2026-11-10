#!/usr/bin/env bash
# Manual deploy on the server checkout: pull main, stop the running bot,
# rebuild the image, start it again. Run from anywhere: scripts/deploy.sh
set -euo pipefail

cd "$(dirname "$0")/.."

# Never deploy over local changes or from another branch.
test -f .env || { echo ".env 파일이 없습니다." >&2; exit 1; }
test "$(git branch --show-current)" = main || { echo "main 브랜치가 아닙니다." >&2; exit 1; }
test -z "$(git status --porcelain)" || { echo "커밋되지 않은 변경이 있습니다." >&2; exit 1; }

git pull --ff-only origin main

# Compose bind-mounts glossary.json; a missing source would be created as a directory.
# Jobs read it as their own UID: readable by all, writable only by its owner.
test -f glossary.json || echo '[]' > glossary.json
chmod 0644 glossary.json

# Only one bot may poll the token: also remove the pre-Compose `docker run` container.
docker rm -f thesis-bot 2>/dev/null || true
docker compose down

docker compose build
docker compose up -d
docker compose ps
echo "배포 완료: $(git rev-parse --short HEAD). 로그: docker compose logs -f thesis-bot"
