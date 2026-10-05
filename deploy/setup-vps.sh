#!/usr/bin/env bash
# One-time setup for a fresh Ubuntu 22.04/24.04 Namecheap VPS. Run as root:
#   bash setup-vps.sh
# Installs Docker, opens only SSH/HTTP/HTTPS in the firewall, adds swap and
# turns on automatic security updates. Safe to run twice.
set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then echo "Run as root (sudo bash setup-vps.sh)"; exit 1; fi

export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y ca-certificates curl git ufw unattended-upgrades

if ! command -v docker >/dev/null; then
  curl -fsSL https://get.docker.com | sh
fi
systemctl enable --now docker

# Firewall: only SSH, HTTP and HTTPS are reachable from the internet.
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw allow 443/udp
ufw --force enable

# 2 GB swap so builds do not run out of memory on small plans.
if ! swapon --show | grep -q .; then
  fallocate -l 2G /swapfile
  chmod 600 /swapfile
  mkswap /swapfile
  swapon /swapfile
  echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi

dpkg-reconfigure -f noninteractive unattended-upgrades || true
echo "Done. Next: clone the repo and fill in .env (see DEPLOY_NAMECHEAP.md)."
