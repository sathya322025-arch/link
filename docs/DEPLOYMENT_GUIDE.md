# Production Linux Server Deployment Guide

This guide covers the deployment of the Secure Remote Device Support platform on **Ubuntu 22.04 / 24.04 LTS** or **Debian 12** using Docker, Docker Compose, Nginx, PostgreSQL, and Coturn.

---

## 1. Server Prerequisites & Firewall Rules

### Recommended Server Specs
- **CPU:** 4 vCPUs or higher
- **RAM:** 8 GB or higher
- **Storage:** 50 GB NVMe SSD
- **Public IP:** Static IPv4 address with DNS records pointing to your domain (e.g., `support.yourcompany.com`)

### Firewall Configuration (UFW)
WebRTC requires specific ports for STUN, TURN, and dynamic UDP relay streams:

```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing

# SSH Access
sudo ufw allow 22/tcp

# Web & WebSocket Reverse Proxy
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp

# Coturn STUN & TURN Signaling
sudo ufw allow 3478/tcp
sudo ufw allow 3478/udp
sudo ufw allow 5349/tcp
sudo ufw allow 5349/udp

# WebRTC Media UDP Relay Port Range
sudo ufw allow 49152:65535/udp

sudo ufw enable
```

---

## 2. Docker & Docker Compose Installation

```bash
# Update repositories and install packages
sudo apt update && sudo apt install -y curl git ufw certbot

# Install Docker Engine
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER

# Verify Docker Compose
docker compose version
```

---

## 3. SSL/TLS Certificate Provisioning (Let's Encrypt)

Before launching the reverse proxy, obtain valid production certificates:

```bash
# Temporarily stop any process on port 80
sudo certbot certonly --standalone \
  -d support.yourcompany.com \
  --agree-tos \
  --email security@yourcompany.com \
  --non-interactive

# Create certificate directory for Docker mount
sudo mkdir -p /opt/remote-support/certs
sudo cp /etc/letsencrypt/live/support.yourcompany.com/fullchain.pem /opt/remote-support/certs/
sudo cp /etc/letsencrypt/live/support.yourcompany.com/privkey.pem /opt/remote-support/certs/
sudo chmod 600 /opt/remote-support/certs/privkey.pem
```

---

## 4. Production Environment Configuration

1. Clone or copy the project files to `/opt/remote-support`.
2. Configure `.env`:
   ```bash
   cp backend/.env.example .env
   ```
3. Generate secure secrets:
   ```bash
   # Generate SECRET_KEY
   python3 -c "import secrets; print(secrets.token_hex(32))"

   # Generate TURN_SECRET
   python3 -c "import secrets; print(secrets.token_hex(24))"
   ```
4. Update the values in `.env` and `coturn/turnserver.conf`.

---

## 5. Launching the Multi-Container Stack

```bash
cd /opt/remote-support

# Build and start services in background
docker compose up -d --build

# Verify container health
docker compose ps
```

Check logs for any service startup issues:
```bash
docker compose logs -f backend
docker compose logs -f coturn
```

---

## 6. Systemd Auto-Start Service

To ensure the entire platform restarts automatically across system updates and reboots:

Create `/etc/systemd/system/remote-support.service`:
```ini
[Unit]
Description=Secure Remote Support Docker Stack
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=/opt/remote-support
ExecStart=/usr/bin/docker compose up -d
ExecStop=/usr/bin/docker compose down
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
```

Enable and activate the unit:
```bash
sudo systemctl daemon-reload
sudo systemctl enable remote-support
```

---

## 7. PostgreSQL Backup & Disaster Recovery

Set up a daily automated database backup cron job:

```bash
# Add to crontab -e
0 2 * * * docker exec support_postgres pg_dump -U support_user remote_support | gzip > /opt/backups/db_$(date +\%F).sql.gz
```

