#!/usr/bin/env bash
# Run on the EC2 box by .github/workflows/deploy.yml, streamed over SSH:
#
#   ssh ubuntu@<host> 'bash -s -- <commit-sha>' < deploy/ci/deploy-backend.sh
#
# Shares the deploy lock with deploy/auto-deploy so two rebuilds never overlap
# on the 2 GB instance. Exits non-zero (failing the GitHub job) when the pull,
# build or health check fails.
set -euo pipefail

SHA=${1:-}
BACKEND_DIR=/opt/lalganjeats

exec 9>/tmp/lalganjeats-deploy.lock
flock -w 1800 9 || { echo "!! another deploy held the lock for 30 minutes" >&2; exit 1; }

cd "$BACKEND_DIR"
git pull --ff-only origin main
if [[ -n $SHA ]] && ! git merge-base --is-ancestor "$SHA" HEAD; then
  echo "!! commit $SHA is not on the server's main after pull" >&2
  exit 1
fi
echo "==> backend at $(git log -1 --format='%h %s')"

docker compose up -d --build
docker image prune -f >/dev/null 2>&1 || true

for _ in $(seq 1 45); do
  if curl -fsS http://127.0.0.1:8000/health >/dev/null 2>&1; then
    echo "==> backend healthy"
    exit 0
  fi
  sleep 2
done

echo "!! backend health check failed" >&2
docker compose logs --tail 80 backend >&2 || true
exit 1
