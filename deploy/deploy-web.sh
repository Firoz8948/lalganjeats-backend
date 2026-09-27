#!/usr/bin/env bash
# Build the Angular web apps from GitHub on this EC2 box and publish them for nginx.
#
#   bash deploy/deploy-web.sh all
#   bash deploy/deploy-web.sh frontend
#   bash deploy/deploy-web.sh live-orders hotel-partner-apk
#
# Source clones live in /opt/<app>; nginx serves /var/www/lalganjeats/<app>.
set -euo pipefail

declare -A REPO=(
  [frontend]=https://github.com/Firoz8948/lalganjeats-frontend.git
  [live-orders]=https://github.com/Firoz8948/live-lalganjeats.git
  [hotel-partner-apk]=https://github.com/Firoz8948/hotel-partner-app.git
  [delivery-partner-apk]=https://github.com/Firoz8948/delivery-partner-app.git
)
declare -A DIST=(
  [frontend]=dist/lalganjeats/browser
  [live-orders]=dist/live-orders/browser
  [hotel-partner-apk]=dist/hotel-partner-app/browser
  [delivery-partner-apk]=dist/delivery-partner-app/browser
)
APPS=(frontend live-orders hotel-partner-apk delivery-partner-apk)

SRC_ROOT=/opt
WEB_ROOT=/var/www/lalganjeats
BRANCH=${BRANCH:-main}

# 2 GB instance shared with the backend container; swap from setup-web.sh covers the rest.
export NODE_OPTIONS=--max-old-space-size=1536

deploy() {
  local app=$1
  local src=$SRC_ROOT/$app

  echo "==> [$app] updating source in $src"
  if [[ ! -d $src/.git ]]; then
    sudo mkdir -p "$src"
    sudo chown "$USER:$USER" "$src"
    git clone --branch "$BRANCH" "${REPO[$app]}" "$src"
  else
    git -C "$src" pull --ff-only origin "$BRANCH"
  fi

  echo "==> [$app] building ($(git -C "$src" log -1 --format='%h %s'))"
  (cd "$src" && npm ci --no-audit --no-fund && npm run build)

  local out=$src/${DIST[$app]}
  if [[ ! -f $out/index.html ]]; then
    echo "!! [$app] build output not found at $out" >&2
    exit 1
  fi

  mkdir -p "$WEB_ROOT/$app"
  rsync -a --delete "$out/" "$WEB_ROOT/$app/"
  echo "==> [$app] published to $WEB_ROOT/$app"
}

if [[ $# -eq 0 ]]; then
  echo "usage: $0 all | ${APPS[*]}" >&2
  exit 1
fi

targets=("$@")
[[ ${targets[0]} == all ]] && targets=("${APPS[@]}")

for app in "${targets[@]}"; do
  if [[ -z ${REPO[$app]:-} ]]; then
    echo "unknown app: $app (expected: all ${APPS[*]})" >&2
    exit 1
  fi
done

for app in "${targets[@]}"; do
  deploy "$app"
done
