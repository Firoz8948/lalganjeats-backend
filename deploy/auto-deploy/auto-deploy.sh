#!/usr/bin/env bash
# Run by the GitHub push webhook (hooks.json) for pushes to main.
#
#   bash auto-deploy.sh <github-repo-name> [commit message]
#
# Returns immediately and deploys in the background so GitHub's 10s webhook
# timeout is never hit. Deploys are serialised with flock: the 2 GB box cannot
# run two Angular builds (or a build plus a docker rebuild) at the same time.
# Put "[skip deploy]" in the commit message to push without deploying.
set -euo pipefail

REPO_NAME=${1:-}
COMMIT_MSG=${2:-}
BACKEND_DIR=/opt/lalganjeats
LOG_DIR=/var/log/lalganjeats-deploy
LOCK_FILE=/tmp/lalganjeats-deploy.lock

case "$REPO_NAME" in
  lalganjeats-backend)  target=backend ;;
  lalganjeats-frontend) target=frontend ;;
  live-lalganjeats)     target=live-orders ;;
  hotel-partner-app)    target=hotel-partner-apk ;;
  delivery-partner-app) target=delivery-partner-apk ;;
  *)
    echo "ignoring push from unknown repository: '$REPO_NAME'" >&2
    exit 0
    ;;
esac

if [[ $COMMIT_MSG == *"[skip deploy]"* ]]; then
  echo "[skip deploy] in commit message; not deploying $target"
  exit 0
fi

if [[ -z ${AUTO_DEPLOY_DETACHED:-} ]]; then
  mkdir -p "$LOG_DIR"
  AUTO_DEPLOY_DETACHED=1 setsid nohup bash "$0" "$@" >>"$LOG_DIR/$target.log" 2>&1 </dev/null &
  echo "deploy of $target queued (log: $LOG_DIR/$target.log)"
  exit 0
fi

exec 9>"$LOCK_FILE"
flock 9

started=$(date +%s)
echo "==== $(date -Is) deploying $target"

if [[ $target == backend ]]; then
  git -C "$BACKEND_DIR" pull --ff-only origin main
  echo "==> backend at $(git -C "$BACKEND_DIR" log -1 --format='%h %s')"
  (cd "$BACKEND_DIR" && docker compose up -d --build)
  docker image prune -f >/dev/null 2>&1 || true
  for _ in $(seq 1 45); do
    if curl -fsS http://127.0.0.1:8000/health >/dev/null 2>&1; then
      echo "==> backend healthy"
      break
    fi
    sleep 2
  done
  curl -fsS http://127.0.0.1:8000/health >/dev/null || { echo "!! backend health check failed" >&2; exit 1; }
else
  bash "$BACKEND_DIR/deploy/deploy-web.sh" "$target"
fi

echo "==== $(date -Is) finished $target in $(( $(date +%s) - started ))s"
