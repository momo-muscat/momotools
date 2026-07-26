# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project overview

momotools is a personal-use Django project run inside Docker (Django + PostgreSQL, nginx reverse
proxy in production). It's deployed at `https://jkmomo.net/momotools/` as one of several projects
sharing that VPS/domain (see "Multi-project hosting" below). Written in Japanese; README.md,
README_DEPLOY.md, and README_VPS.md contain the full setup/deploy/VPS history in Japanese and are
the source of truth for anything infrastructure-related not covered here.

Dependencies are managed with `uv` (not pip/poetry directly); the lockfile is `uv.lock`.

## Commands

All commands run inside the `web` container (or via `uv run` if working directly on the host with
`uv` installed). In the Dev Container, the `web` service already runs `runserver` as PID 1, so
don't try to start it again on the default port.

```bash
# Run dev server on an alternate port (PID 1 already holds 8000)
uv run python manage.py runserver 0.0.0.0:8001

# Migrations
uv run python manage.py makemigrations
uv run python manage.py migrate

# Create an app
uv run python manage.py startapp <app_name>

# Tests (per-app tests.py, standard Django test runner)
uv run python manage.py test
uv run python manage.py test top_page
uv run python manage.py test top_page.tests.SomeTestCase.test_some_method  # single test

# Lint / format
uv run ruff check .
uv run black --check .
uv run pre-commit install   # one-time, runs ruff+black on commit
```

Outside the container (host machine, from scratch):

```bash
sudo docker compose up --build -d
sudo docker compose exec web python manage.py migrate
```

Production uses an override compose file — always include both when starting/rebuilding in prod,
otherwise it falls back to the dev `runserver` CMD from the Dockerfile:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
docker compose exec web python manage.py migrate
docker compose exec web python manage.py collectstatic --noinput
```

## Architecture

- Single Django project `config/` with one app per feature area; currently only `top_page` exists
  (a placeholder landing page — `TemplateView` rendering `top_page/index.html`, no models yet).
- **URL mounting is not at root.** `config/urls.py` mounts everything under `/momotools/`
  (`momotools/admin/` for the admin site, `momotools/` for `top_page.urls`). This is deliberate:
  the VPS hosts multiple unrelated projects under one domain via nginx path-based routing, and this
  project owns the `/momotools/` path segment. When adding new apps/views, keep them under this
  project's URL namespace rather than assuming root-mounted routes.
- Settings (`config/settings.py`) are environment-driven via `django-environ`, reading from `.env`
  (gitignored; copy from `.env.example`). Key env vars: `DEBUG`, `DJANGO_SECRET_KEY`,
  `DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_TRUSTED_ORIGINS`, `DATABASE_URL`, plus `POSTGRES_*` for the
  db container. `DATABASE_URL` falls back to local sqlite if unset. `LANGUAGE_CODE` is `ja`,
  `TIME_ZONE` is `Asia/Tokyo`.
- `SECURE_PROXY_SSL_HEADER` is set because nginx terminates TLS and proxies to Django over plain
  HTTP — Django trusts `X-Forwarded-Proto` to detect HTTPS. Don't remove this without also
  reconsidering the nginx config.
- Dev vs prod differ only via `docker-compose.prod.yml`: prod overrides the `web` command to run
  gunicorn (`config.wsgi:application`) instead of the Dockerfile's default `runserver`, and sets
  `restart: always`. Both `db` and `web` ports are bound to `127.0.0.1` only in both configs —
  external access always goes through host nginx, never directly to the containers.
- Templates use Tailwind via CDN script tag (no build pipeline) — see
  `top_page/templates/top_page/index.html` for the current pattern.
- `scripts/backup_db.sh` does daily PostgreSQL backups via `docker compose exec db pg_dump`
  (reusing the container's own env vars, no duplicated credentials), rotating old dumps into
  `~/momo/backup/old/` with 90-day retention; registered via cron on the VPS, not in-repo.

## Multi-project hosting (VPS)

This app is one of potentially several projects sharing one VPS/nginx/domain. The convention
(documented in full in README_VPS.md) is: one project = one container (or static dir) on its own
internal port bound to `127.0.0.1`, with nginx routing `location /project-name/` to it. Each new
project gets its own Postgres database name even if sharing the same Postgres server. Don't assume
this project can bind to a public port or own the domain root.
