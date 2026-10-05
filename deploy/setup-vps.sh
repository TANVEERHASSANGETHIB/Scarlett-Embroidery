#!/usr/bin/env bash
# One-time setup for a fresh Namecheap VPS (Ubuntu/Debian or AlmaLinux/Rocky/CentOS). Run as root:
#   bash deploy/setup-vps.sh
# Installs Docker + make, opens only SSH/HTTP/HTTPS in the firewall, adds swap and
# turns on automatic security updates. Safe to run twice.
set -euo pipefail

if [ "$(id -u)" -ne 0 ]; then echo "Run as root"; exit 1; fi

if command -v apt-get >/dev/null; then
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -y
  apt-get install -y ca-certificates curl git make ufw unattended-upgrades
  if ! command -v docker >/dev/null; then curl -fsSL https://get.docker.com | sh; fi
  ufw allow OpenSSH
  ufw allow 80/tcp
  ufw allow 443/tcp
  ufw allow 443/udp
  ufw --force enable
  dpkg-reconfigure -f noninteractive unattended-upgrades || true
elif command -v dnf >/dev/null; then
  dnf install -y git make curl dnf-plugins-core dnf-automatic firewalld
  if ! command -v docker >/dev/null; then
    dnf config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
    dnf install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
  fi
  systemctl enable --now firewalld
  firewall-cmd --permanent --add-service=ssh
  firewall-cmd --permanent --add-service=http
  firewall-cmd --permanent --add-service=https
  firewall-cmd --permanent --add-port=443/udp
  firewall-cmd --reload
  systemctl enable --now dnf-automatic-install.timer || true
else
  echo "Unsupported system: needs apt (Ubuntu/Debian) or dnf (AlmaLinux/Rocky/CentOS)."; exit 1
fi

systemctl enable --now docker

# 2 GB swap so builds do not run out of memory on small plans.
if ! swapon --show | grep -q .; then
  fallocate -l 2G /swapfile || dd if=/dev/zero of=/swapfile bs=1M count=2048
  chmod 600 /swapfile
  mkswap /swapfile
  swapon /swapfile
  echo '/swapfile none swap sw 0 0' >> /etc/fstab
fi

docker --version && docker compose version
echo "Done. Next: create .env and run 'make prod-up' (see DEPLOY_NAMECHEAP.md)."
