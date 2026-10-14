#!/usr/bin/env bash
set -euo pipefail

# Swap file is mandatory on a 1GB VPS
if ! swapon --show | grep -q /swapfile; then
  fallocate -l 2G /swapfile
  chmod 600 /swapfile
  mkswap /swapfile
  swapon /swapfile
  echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi

apt-get update
apt-get install -y ca-certificates curl ufw
curl -fsSL https://get.docker.com | sh

ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable

mkdir -p files n8n_data caddy_data
chown -R 1000:1000 n8n_data files
