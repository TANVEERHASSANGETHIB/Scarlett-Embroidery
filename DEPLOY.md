> **Namecheap VPS?** Follow [DEPLOY_NAMECHEAP.md](DEPLOY_NAMECHEAP.md) — it covers DNS, server setup, HTTPS and backups step by step.

# Deploying Scarlett Embroidery to production

Needs a Linux server (Ubuntu 22.04+ is fine) with Docker and Docker Compose, and a domain pointing at the server's IP.

## 1. Get the code and configure
```bash
git clone https://github.com/tanveerhassangethib/scarlett-embroidery.git
cd scarlett-embroidery
git checkout main            # or the branch you merged the changes into
cp .env.production.example .env
nano .env                    # replace every CHANGE_ME, set your domain
```
Generate the secret key with `python3 -c "import secrets; print(secrets.token_urlsafe(64))"`.

## 2. Start it
```bash
make prod-up        # builds, runs migrations, serves on port 80
make prod-seed      # FIRST RUN ONLY: pricing, patch categories, first admin
```
No `make`? Use: `docker compose -f docker-compose.prod.yml up -d --build`, then
`docker compose -f docker-compose.prod.yml exec web python manage.py seed --no-demo`.

## 3. HTTPS
Caddy (part of the stack) gets the certificate automatically once `DOMAIN` in `.env` points at the server and ports 80/443 are open. Keep `SECURE_SSL_REDIRECT=True` and `SECURE_COOKIES=True`. After a few days raise `SECURE_HSTS_SECONDS` to `31536000`.

## 4. Check it
```bash
make check          # Django deploy checks (should report no issues)
make prod-logs      # tail logs
```
Sign in at https://yourdomain.com/console/, then change the admin password (Settings → My account) and set order-alert emails (Settings → Notifications → "Send test email").

## 5. Backups and updates
- Back up the Docker volumes `pgdata` (database), `media` (public images) and `private_media` (customer files). Database dump: `docker compose -f docker-compose.prod.yml exec db pg_dump -U scarlett scarlett > backup.sql`.
- Update: `git pull && make prod-up` (migrations run automatically).
- Remove unfinished guest drafts regularly: `docker compose -f docker-compose.prod.yml exec web python manage.py purge_drafts` (e.g. weekly cron).
