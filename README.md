# Scarlett Embroidery

Website and back office for Scarlett Embroidery. The public site covers embroidery digitizing, vector art and custom patches, with customer accounts, online ordering, real-time live chat and an admin console.
It's built with Django 5.2, Channels (WebSockets), PostgreSQL and Redis, and runs in Docker.

## Quick start (development)

```bash
make up        # builds and starts web, PostgreSQL, Redis and Mailpit; runs migrations
make seed      # pricing tiers, patch categories, demo content and the first admin account
```

| What | URL |
|---|---|
| Website | http://localhost:8000 |
| Admin console | http://localhost:8000/console/ (login uses `ADMIN_EMAIL` / `ADMIN_PASSWORD` from `.env`) |
| Mailpit (every email sent in dev, including verification codes) | http://localhost:8025 |
| Django data admin (superusers) | http://localhost:8000/django-admin/ |

If port 8000, 5432 or 8025 is already in use, change `WEB_PORT`, `POSTGRES_PORT` or `MAILPIT_PORT` in `.env`.

Run `make help` to list every command. The common ones:

```bash
make test      # pytest suite (unit, integration and WebSocket tests)
make lint      # ruff
make format    # ruff format and autofix
make logs      # tail the web container
make shell     # Django shell
make clean     # stop and DELETE the dev database and uploads
```

## Features

**Public site**: home, portfolio (filterable), about, contact form (saved to the inbox and emailed to staff), blog with articles, privacy policy and terms.

**Customer accounts**
- Sign up with email and password. A **6-digit verification code** is emailed and must be entered before the account can be used. Codes expire after 15 minutes, lock after 5 wrong attempts, and can be resent after a 60-second cooldown.
- Log in, reset a forgotten password, edit the profile, change the password. Changing the email address requires verifying it again.
- Dashboard with stats, order search, and an order detail page with a timeline, artwork uploads, proof approval or revision requests, and downloads of the final files.

**Place order** — open to everyone; an account is only needed to send it
- A visitor can fill in the whole form, artwork included, without signing in. When they press **Place order** a dialog asks them to log in or create an account, and explains that their work is saved.
- Everything they entered — including uploaded files — is kept against their browser session. After logging in (or creating an account and entering the emailed code) they land back on the order form with every field and file exactly as they left it, and can send it in one click.
- Saved drafts belong to that one session, are never visible to anyone else, and are deleted as soon as the order is placed. Anything left unfinished is removed after 14 days (`make shell` or cron: `python manage.py purge_drafts`).
- **Digitizing** uses flat pricing per design type: Left chest $6, Full back $10, Complex design $15. Optional rush surcharges apply. The form also asks for fabric, placement, size and file formats.
- **Vector art** uses a flat price per logo and asks for vector formats.
- **Patches** ask for:
  - patch category (Iron-on / Embroidery / Rubber)
  - backing (iron-on, velcro, adhesive, sew-on)
  - quantity (minimum 50) and size
  - full **shipping address**
- Every service has an **instruction box** and multi-file artwork upload (25 MB per file, file type checked).
- The estimate updates live in the browser and is recalculated on the server when the order is saved.
- Uploaded files are stored privately and are only downloadable by the order's owner or staff.

**Live chat**: a real-time WebSocket widget on every public page. Guests can leave a name and email. Visitor details (IP, device, current page, referrer) are tracked.

**Admin console** (`/console/`, email and password)
- **Live chat**: conversation list with filters and 10/20/50 per page, real-time replies, assign, close or reopen, export transcript, block an IP.
- **Orders**: queue sorted unassigned-first and then by due date. Staff can set status, final price, payment status and the assigned digitizer, add internal notes or send messages to the customer, and upload proofs and final files. Status changes email the customer automatically.
- **Customers**: search, order history and spend, disable an account, mark an email as verified.
- **Inbox**: contact form messages.
- **Portfolio**: upload sew-out photos (several at once), file each under a category (Caps, Left chest, Jacket back, Patches, Vector), edit the name, category, caption or photo, hide one from the site, or delete it along with its file. Tick “feature in the home page showcase” to include a piece in the home page sew-out showcase, with its spec sheet.
- **Reviews**: add, edit, hide or delete customer quotes (stars, name, role, order). They feed the auto-scrolling carousel on the home page.
- **Blogs**: Markdown editor with cover image, draft or publish, featured post.
- **Appearance**: a dark/light toggle at the bottom of the console sidebar (moon = dark, sun = light). The choice applies instantly, is saved to that admin's account, and follows them to every console page and device. Each admin has their own; it doesn't affect the public website.
- **Settings**: a tabbed screen where everything is edited in place — **Pricing**, **Turnaround**, **Patches** (add, edit and remove rows, each with an active toggle and sort order), **Notifications**, **Site details**, **Team** (invite or disable admins) and **Security** (blocked IPs). Each section saves on its own and shows an "unsaved changes" hint while you edit.

## Contact map

The contact page ends with a full-width map band. Set it in **Console → Settings → Site details**:

- **Business name** and **Studio address** — the address is listed in the contact details and the map drops a pin labelled with the business name.
- **Custom map embed URL** — optional. Google Maps → Share → Embed a map, then paste the `src`. It takes priority over the address.
- **Show the map on the contact page** — hides the map while keeping the address.

Nothing is shown until an address is entered. The map loads from Google, so it appears a moment after the rest of the page.

## Order alert emails

Order emails are routed by purpose:
- **Order details and artwork** — `scarletsembroidery@gmail.com` receives the complete order specification in a structured email, the submitted artwork as attachments, and a link to the order in the console. Replies go to the customer.
- **New-order notice** — `info@sedigitizer.com` receives a short notice when an order is submitted. This notice can be switched off without stopping delivery of the full order details.
- **Contact form** — `support@sedigitizer.com` receives the form submission and can reply directly to the sender.

Manage this in **Console → Settings → Notifications**:
- **New-order notice recipients**, **Order details and artwork recipients**, and **Contact form recipients** — configure each route independently; separate multiple addresses with commas.
- **Email me about new orders** — turn the short notice on or off; full order details continue to be sent.
- **Send yourself a test** — delivers a sample notice to the new-order notice recipients.

The tab also shows which mail server is in use, the sending account and whether the password is stored — but never the password itself.

### Mail credentials

Sending credentials live only in `.env`, which is listed in `.gitignore` and must never be committed. They are never written into code, shown in the admin console, or included in logs:

```env
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=you@gmail.com
EMAIL_HOST_PASSWORD=your-16-char-app-password
DEFAULT_FROM_EMAIL=Scarlett Embroidery <you@gmail.com>
```

For Gmail, use an **App Password** (Google Account → Security → 2-Step Verification → App passwords), never the account's normal password. An app password can be revoked from that page at any time without changing your Google password — do that if it is ever exposed, then update `.env` and restart (`make restart`).

Leave `EMAIL_HOST` empty to send to the local Mailpit dev inbox instead of real addresses.

Delivery runs on a background thread and retries up to three times, so a slow mail server never delays the customer's page and a brief network failure doesn't lose the alert. Failures are logged (`make logs`).

## Payments

There is no payment gateway. Orders are quoted and invoiced: the admin sets the final price and marks the order Paid or Waived. A gateway such as Stripe can be added later.

## Project layout

```
Dockerfile, docker-compose.yml, docker-compose.prod.yml, Makefile
docker/            entrypoint (waits for DB and Redis, runs migrations) and the Caddy config
requirements/      base / dev / prod
src/
  config/          settings (base, dev, prod, test), urls, asgi (HTTP + WebSocket routing)
  apps/core        public pages, site settings, portfolio, testimonials, FAQ, contact, `seed` command
  apps/accounts    email-based User, verification codes, auth, profile, dashboard
  apps/orders      pricing, orders, patch details, private files, order timeline, emails
  apps/blog        posts and categories (Markdown, sanitised)
  apps/chat        chat sessions and messages, WebSocket consumers, blocked IPs
  apps/console     admin console views
  templates/       site, account, console and email templates
  static/          CSS design system, JS (order form, chat widget, console chat), fonts, logo
```

## Production

1. Copy `.env.example` to `.env` and set at least these values:
   - `DEBUG=False`
   - a long random `SECRET_KEY`
   - `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS` for your domain
   - `SITE_URL=https://yourdomain`
   - a strong `POSTGRES_PASSWORD`, with `DATABASE_URL` updated to match
   - real mail credentials (`EMAIL_HOST`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`) — see **Mail credentials** above
   - `STAFF_NOTIFY_EMAIL` and a strong `ADMIN_PASSWORD`
2. Behind HTTPS, also set `SECURE_SSL_REDIRECT=True`, `SECURE_COOKIES=True` and `SECURE_HSTS_SECONDS=31536000`.
3. Run:

```bash
make prod-up       # daphne (ASGI) behind Caddy with automatic HTTPS (80/443)
make prod-seed     # pricing + first admin (no demo content)
```

The production stack listens on **http://localhost** (port 80), not the dev port, and keeps its **own database** — separate from development. On a fresh production database nothing exists yet, so `make prod-seed` is required before you can sign in to the console; without it the login will reject every password because no admin account exists. Content (portfolio, reviews, settings) is likewise per-stack.

In production, Caddy serves public media, proxies `/ws/` WebSockets and gets the HTTPS certificate. Static files are served by WhiteNoise, and customer files are streamed only after a permission check.

## Recent additions

- **Quote page** (`/order/quote/`): same questions as the order form, but no prices are shown or stored. Quotes are numbered `QT-…` and can be filtered in the console (Orders → Quotes).
- **Services pages** (`/services/`, `/services/embroidery|vector|patches/`), a **Testimonials page**, and a new header menu (Services and More dropdowns).
- **Home pricing tabs** (Embroidery / Vector / Patches). Edit the cards under Console → Settings → Pricing and Patches (ribbon, features, highlight).
- **Portfolio categories** are managed in Console → Portfolio → Categories.
- **Footer social icons**: Console → Settings → Social links.
- **Admin password change**: Console → Settings → My account.
- Uploads show a progress bar and per-file "Attached / Uploaded" status; hero numbers count up on page load.
- **Media** (Console → Media): before/after sliders for the Embroidery and Vector pages, service pictures, and photos for Home/About. Empty spots show built-in artwork. Testimonials accept an optional photo.
- Site font is Poppins (self-hosted in `static/fonts`). The live-chat button is now a round icon.
