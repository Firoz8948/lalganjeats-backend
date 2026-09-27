#!/usr/bin/env bash
# One-time EC2 setup for serving the Angular web apps next to the API.
# Safe to re-run: it never overwrites the installed nginx site (certbot edits that copy).
#
#   cd /opt/lalganjeats && bash deploy/setup-web.sh
set -euo pipefail

DEPLOY_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)

if ! swapon --show | grep -q '^/swapfile'; then
  echo "==> adding 2G swap (Angular builds need more than the free RAM)"
  sudo fallocate -l 2G /swapfile
  sudo chmod 600 /swapfile
  sudo mkswap /swapfile
  sudo swapon /swapfile
  grep -q '^/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
fi

if ! command -v node >/dev/null || [[ $(node -v) != v22.* ]]; then
  echo "==> installing Node.js 22"
  curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
  sudo apt-get install -y nodejs
fi
command -v rsync >/dev/null || sudo apt-get install -y rsync

sudo mkdir -p /var/www/lalganjeats
sudo chown "$USER:$USER" /var/www/lalganjeats

sudo cp "$DEPLOY_DIR/nginx/lalganjeats-spa.conf" /etc/nginx/snippets/lalganjeats-spa.conf
if [[ ! -f /etc/nginx/sites-available/lalganjeats-web ]]; then
  sudo cp "$DEPLOY_DIR/nginx/lalganjeats-web.conf" /etc/nginx/sites-available/lalganjeats-web
fi
sudo ln -sf /etc/nginx/sites-available/lalganjeats-web /etc/nginx/sites-enabled/lalganjeats-web

sudo nginx -t
sudo systemctl reload nginx

echo "==> done. Next: bash deploy/deploy-web.sh all"
