# Deploy on a Namecheap VPS (Ubuntu + Docker + Caddy)

You end up with: `https://yourdomain.com` served by Caddy (free auto-renewing HTTPS) → the Django app (Daphne) → PostgreSQL + Redis, all in Docker on your VPS. Nothing else needs installing by hand.

**Before you start you need:** the VPS IP address, its root login (Namecheap emails it, or it is under *Products → VPS → Manage*), and the domain. A plan with 2 GB RAM or more is comfortable; 1 GB works with the swap the setup script adds.

## 1. Point the domain at the VPS (Namecheap)
Namecheap → *Domain List → Manage → Advanced DNS*. Under *Host Records* delete the parking-page records and add:

| Type | Host | Value |
|------|------|-------|
| A Record | `@`   | your VPS IP |
| A Record | `www` | your VPS IP |

If the domain's nameservers are "Namecheap BasicDNS" (the default) this is all you need. DNS can take from a few minutes to a few hours; `ping yourdomain.com` should show your VPS IP before step 4.

## 2. Prepare the server (once)
```bash
ssh root@YOUR_VPS_IP
git clone https://github.com/tanveerhassangethib/scarlett-embroidery.git /opt/scarlett-embroidery
cd /opt/scarlett-embroidery
git checkout main
bash deploy/setup-vps.sh        # Docker, firewall (22/80/443), swap, auto security updates
```

## 3. Configure
```bash
cp .env.production.example .env
nano .env
```
Replace every `CHANGE_ME` and every `yourdomain.com`:
- `SECRET_KEY` — `python3 -c "import secrets; print(secrets.token_urlsafe(64))"`
- `POSTGRES_PASSWORD` — and the same password inside `DATABASE_URL`
- `ADMIN_EMAIL` / `ADMIN_PASSWORD` — your first login to `/console/`
- `DOMAIN`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, `SITE_URL`
- Email (`EMAIL_*`): order alerts and sign-in codes are sent from here. With Namecheap Private Email use `EMAIL_HOST=mail.privateemail.com`, `EMAIL_PORT=587`, `EMAIL_HOST_USER=<your mailbox>`; Gmail needs an App Password.

`.env` holds your passwords. Never commit it (it is git-ignored).

## 4. Start
```bash
make prod-up        # builds, migrates, starts everything; Caddy fetches the HTTPS certificate
make prod-seed      # first run only: pricing, patch categories, the admin account
```
No `make`? `apt install make`, or use `docker compose -f docker-compose.prod.yml up -d --build` and `... exec web python manage.py seed --no-demo`.

Open `https://yourdomain.com`. If the certificate fails, DNS has not reached the server yet; wait and run `docker compose -f docker-compose.prod.yml logs caddy`.

## 5. First things to do in the Console (`/console/`)
1. Change the admin password (Settings → My account).
2. Settings → Contact: **replace the placeholder phone number, emails, hours and address** (the defaults are fake `555` numbers), add social links.
3. Settings → Notifications: set the order-alert email and press "Send test email".
4. Upload your real photos (home page slots, portfolio, Client sew-outs, reviews) and write blog posts.
5. Optional: `make prod-up` after setting `SECURE_HSTS_SECONDS=31536000` once everything has worked for a few days.

## 6. Backups and updates
```bash
# nightly backup (database + uploads, keeps 14 days in /opt/scarlett-backups)
( crontab -l 2>/dev/null; echo "15 3 * * * /opt/scarlett-embroidery/deploy/backup.sh >> /var/log/scarlett-backup.log 2>&1" ) | crontab -
# weekly cleanup of abandoned guest orders
( crontab -l 2>/dev/null; echo "30 3 * * 0 cd /opt/scarlett-embroidery && docker compose -f docker-compose.prod.yml exec -T web python manage.py purge_drafts" ) | crontab -
```
Also copy `/opt/scarlett-backups` somewhere off the server occasionally. A backup on the same machine does not survive losing the VPS.

Update the site after a new version is pushed to `main`:
```bash
cd /opt/scarlett-embroidery && git pull && make prod-up
```
Migrations run automatically. Uploaded photos and the database live in Docker volumes and are not touched by updates.

## Troubleshooting
- `make prod-logs` shows the app and Caddy logs.
- Login or forms fail with "CSRF verification failed": `CSRF_TRUSTED_ORIGINS` must be `https://yourdomain.com,https://www.yourdomain.com`.
- Live chat does not connect: make sure nothing else (a Cloudflare proxy with WebSockets off) sits in front of Caddy.
- Emails not arriving: Console → Settings → Notifications → "Send test email" shows the error.
