# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

momotools is a personal-use Django project (Django + PostgreSQL, nginx reverse proxy in
production). It's deployed at `https://jkmomo.net/momotools/` as one of several projects sharing
that VPS/domain (see "Multi-project hosting" below). Written in Japanese; README.md,
README_DEPLOY.md, and README_VPS.md contain the full setup/deploy/VPS history in Japanese and are
the source of truth for anything infrastructure-related not covered here.

Dependencies are managed with `uv` (not pip/poetry directly); the lockfile is `uv.lock`. There is
no Docker/container layer — dev and prod both run directly on the host (WSL2 locally, a systemd
service on the VPS) against a natively-installed PostgreSQL.

## Commands

```bash
# Run dev server
uv run python manage.py runserver 0.0.0.0:8000

# Migrations
uv run python manage.py makemigrations
uv run python manage.py migrate

# Create an app (apps live under app/, not the project root — see README.md for the full steps,
# including the apps.py `name` and INSTALLED_APPS/urls.py fixups this requires)
uv run python manage.py startapp <app_name> app/<app_name>

# Tests (per-app tests.py, standard Django test runner)
uv run python manage.py test
uv run python manage.py test app.top_page
uv run python manage.py test app.top_page.tests.SomeTestCase.test_some_method  # single test

# Lint / format
uv run ruff check .
uv run black --check .
uv run pre-commit install   # one-time, runs ruff+black on commit
```

Production deploy (VPS, via SSH — see README_DEPLOY.md for the full procedure):

```bash
git pull
uv sync
uv run python manage.py migrate
uv run python manage.py collectstatic --noinput
sudo systemctl restart momotools
```

## Architecture

- Single Django project `config/` with one app per feature area, all living under `app/`
  (e.g. `app/top_page/`); currently only `top_page` exists (a placeholder landing page —
  `TemplateView` rendering `top_page/index.html`, no models yet). `INSTALLED_APPS` and imports use
  the dotted path `app.top_page`, but the Django app label (used by `manage.py test`, migrations,
  etc.) stays the last component, `top_page`.
- **URL mounting is not at root.** `config/urls.py` mounts everything under `/momotools/`
  (`momotools/admin/` for the admin site, `momotools/` for `app.top_page.urls`). This is deliberate:
  the VPS hosts multiple unrelated projects under one domain via nginx path-based routing, and this
  project owns the `/momotools/` path segment. When adding new apps/views, keep them under this
  project's URL namespace rather than assuming root-mounted routes.
- Settings (`config/settings.py`) are environment-driven via `django-environ`, reading from `.env`
  (gitignored; copy from `.env.example`). Key env vars: `DEBUG`, `DJANGO_SECRET_KEY`,
  `DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_TRUSTED_ORIGINS`, `DATABASE_URL`. `LANGUAGE_CODE` is `ja`,
  `TIME_ZONE` is `Asia/Tokyo`.
- **Database auth differs between local and prod on purpose.** Locally, PostgreSQL is reached over
  a Unix socket with peer authentication — the Postgres role name must match your OS username (e.g.
  `postgres://momo@//var/run/postgresql/momotools`), so there's no local password to manage. In
  production, it's TCP + password (`postgres://user:pass@127.0.0.1:5432/dbname`) since the app runs
  under a fixed service user (`ubuntu`) via systemd. `POSTGRES_DB`/`POSTGRES_USER`/
  `POSTGRES_PASSWORD` in `.env` are only consumed by `scripts/backup_db.sh` on the VPS (TCP auth for
  `pg_dump`), not by Django itself.
- `SECURE_PROXY_SSL_HEADER` is set because nginx terminates TLS and proxies to Django over plain
  HTTP — Django trusts `X-Forwarded-Proto` to detect HTTPS. Don't remove this without also
  reconsidering the nginx config.
- In production, gunicorn (`config.wsgi:application`) runs as a systemd service (`momotools.service`)
  bound to `127.0.0.1:8000`; nginx is the only thing that talks to it. Locally, `manage.py runserver`
  is used directly — there's no process manager needed for dev.
- Templates use Tailwind via CDN script tag (no build pipeline) — see
  `app/top_page/templates/top_page/index.html` for the current pattern. A parallel Jinja2 backend
  is also configured (`config/jinja2.py`), rooted at the project-level `jinja2/` directory (not
  per-app) since there's only one app so far — see README.md for details.
- `scripts/backup_db.sh` does daily PostgreSQL backups via a direct `pg_dump` against the native
  Postgres instance (TCP, credentials from `.env`), rotating old dumps into `~/momo/backup/old/`
  with 90-day retention; registered via cron on the VPS, not in-repo.

## Multi-project hosting (VPS)

This app is one of potentially several projects sharing one VPS/nginx/domain. The convention
(documented in full in README_VPS.md) is: one project = one process (systemd service or static
dir) on its own internal port bound to `127.0.0.1`, with nginx routing `location /project-name/` to
it. Each new project gets its own Postgres database (and typically its own role) even if sharing
the same native Postgres server. Don't assume this project can bind to a public port or own the
domain root.
