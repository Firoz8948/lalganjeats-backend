#!/usr/bin/env bash
# One-time setup of push-to-deploy on the EC2 box. Safe to re-run.
#
#   bash /opt/lalganjeats/deploy/auto-deploy/setup-auto-deploy.sh
#
# Installs adnanh/webhook as a systemd service on 127.0.0.1:9000 and exposes it
# through nginx as https://api.lalganjeats.com/hooks/deploy. Prints the GitHub
# webhook secret at the end (generated once, kept in /etc/lalganjeats/webhook.env).
set -euo pipefail

HERE=$(cd "$(dirname "$0")" && pwd)
ENV_FILE=/etc/lalganjeats/webhook.env
NGINX_SITE=/etc/nginx/sites-available/lalganjeats-api
NGINX_SNIPPET=/etc/nginx/snippets/lalganjeats-hooks.conf
LOG_DIR=/var/log/lalganjeats-deploy

echo "==> installing webhook"
command -v webhook >/dev/null || sudo apt-get install -y webhook
sudo systemctl disable --now webhook.service >/dev/null 2>&1 || true

echo "==> secret"
sudo mkdir -p /etc/lalganjeats
if ! sudo test -f "$ENV_FILE"; then
  echo "WEBHOOK_SECRET=$(openssl rand -hex 32)" | sudo tee "$ENV_FILE" >/dev/null
fi
sudo chown root:ubuntu "$ENV_FILE"
sudo chmod 640 "$ENV_FILE"

sudo mkdir -p "$LOG_DIR"
sudo chown ubuntu:ubuntu "$LOG_DIR"

echo "==> systemd unit"
sudo cp "$HERE/lalganjeats-webhook.service" /etc/systemd/system/lalganjeats-webhook.service
sudo systemctl daemon-reload
sudo systemctl enable --now lalganjeats-webhook.service
sudo systemctl restart lalganjeats-webhook.service

echo "==> nginx /hooks/ route"
sudo tee "$NGINX_SNIPPET" >/dev/null <<'NGINX'
location /hooks/ {
    proxy_pass http://127.0.0.1:9000/hooks/;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_read_timeout 15s;
}
NGINX
if ! sudo grep -q "lalganjeats-hooks.conf" "$NGINX_SITE"; then
  backup="$NGINX_SITE.bak.$(date +%s)"
  sudo cp "$NGINX_SITE" "$backup"
  # First server block is the certbot-managed 443 one for api.lalganjeats.com.
  sudo sed -i '0,/client_max_body_size[^;]*;/s//&\n\n    include snippets\/lalganjeats-hooks.conf;/' "$NGINX_SITE"
  if ! sudo nginx -t; then
    echo "!! nginx config test failed; restoring $backup" >&2
    sudo cp "$backup" "$NGINX_SITE"
    exit 1
  fi
fi
sudo nginx -t
sudo systemctl reload nginx

sleep 1
systemctl is-active --quiet lalganjeats-webhook.service && echo "==> webhook service running"
echo
echo "GitHub webhook settings (add to each repo → Settings → Webhooks):"
echo "  Payload URL:  https://api.lalganjeats.com/hooks/deploy"
echo "  Content type: application/json"
echo "  Secret:       $(sudo sed -n 's/^WEBHOOK_SECRET=//p' "$ENV_FILE")"
echo "  Events:       Just the push event"
