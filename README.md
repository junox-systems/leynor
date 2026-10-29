# Django 5.2 LTS Starter Kit

A modern, production-ready Django starter kit — opinionated, lean, and ready to build on.

## What's Inside

### Backend

| Package | Purpose |
|---------|---------|
| **Django 5.2 LTS** | Core framework |
| **PostgreSQL 18** (ParadeDB image) | Database, BM25/vector search (`django-paradedb`), cache, settings and task queue |
| **Granian** | Production ASGI server (Rust-based, async-native) |
| **Whitenoise** | Static file serving |
| **django-allauth** | Auth — local accounts, OIDC/SSO, social login |
| **django-auditlog** | Automatic model change tracking |
| **Organizations + RBAC** (`apps/orgs`) | Teams, email invitations, role-based access control after ANSI INCITS 359-2004 |
| **django-imagekit** | On-demand image processing (avatar thumbnails) |
| **django-storages** | Media backend chosen by `STORAGE_BACKEND`: local disk, S3, Azure or GCS |
| **django-anymail** | Transactional email via Resend (or any SMTP server) |
| **django-q2** | Background tasks + schedules, Postgres as broker |
| **Sentry SDK** | Error tracking + performance monitoring (opt-in) |
| **OpenTelemetry** | Distributed tracing — Django, psycopg (opt-in) |

### Frontend

| Package | Purpose |
|---------|---------|
| **django-cotton** | Server-rendered template components (`<c-card>`, `<c-btn>`, `<c-form>`) |
| **htmx 4** | Boosted navigation inside the app shell |
| **Stimulus 3** | Controller glue — mounts Svelte components, handles DOM behaviour |
| **Svelte 5** | Interactive islands (for high-interactivity UI) |
| **GSAP 3** | Animations and transitions |
| **Tailwind CSS v4** | Utility-first styling |
| **Basecoat CSS** | Component library (shadcn-compatible tokens) |
| **Vite** | Asset bundler with HMR |

### Developer Tools

| Tool | Purpose |
|------|---------|
| **uv** | Fast Python package manager |
| **pnpm** | Fast JS package manager (Node 24) |
| **ruff** | Linter + formatter |
| **pytest** | Testing framework |
| **django-debug-toolbar** | Query analysis in development |
| **just** | Task runner (`justfile`; the `Makefile` mirrors it) |
| **Docker + mise** | Reproducible dev environment (Debian trixie-slim: x86-64 v1+ and arm64) |

---

## Quick Start

### Prerequisites

- Docker and Docker Compose ([OrbStack](https://orbstack.dev/) recommended on macOS)

### Dockerised (all-in-one)

```bash
git clone <repository-url>
cd django-starter-kit

cp .env.example .env   # optional: every key has a dev default

just dev               # db, Django, Vite, qcluster + ClickStack analytics
just logs              # follow logs
just dev-createsuperuser   # admin@example.com / admin
```

Migrations run automatically every time the app container starts.

Without analytics (lighter, OTEL off):

```bash
just dev-slim          # db + app only
```

ClickStack UI: http://localhost:8080 (no login, local mode).
OTLP endpoint: http://localhost:4318 (HTTP) / http://localhost:4317 (gRPC).

Dev keeps media on local disk (`media/`). S3 is configured only in the
production stack.

---

## Organizations & Access Control

Every account starts with a personal organization (`<username>'s workspace`). Users join more through email invitations and switch between them in the app bar. The dashboard shows the current one.

Access inside an organization is **role-based access control (RBAC)**. It is modeled on:

> **ANSI INCITS 359-2004**, *American National Standard for Information Technology – Role Based Access Control*. American National Standards Institute / InterNational Committee for Information Technology Standards, 2004. Superseded by INCITS 359-2012 (R2022).
>
> - Text: <https://www.cs.purdue.edu/homes/ninghui/readings/AccessControl/ANSI+INCITS+359-2004.pdf>
> - NIST RBAC project (adoption, title, history): <https://csrc.nist.gov/projects/role-based-access-control>

Implemented components: **Core RBAC** (§5.1, §6.1) and **Limited Role Hierarchies** (§5.2, §6.2.2). Separation-of-duty constraints (§5.3) are optional in the standard and not implemented. This is a design reference, not a certified compliance claim.

| Default role | Inherits | Adds |
|---|---|---|
| `owner` | admin | delete the organization (`change_organization` reserved for org settings) |
| `admin` | member | invite people, assign roles, remove members |
| `member` | — | view the organization |

- Roles and their permissions are data: edit them in the admin under *Orgs → Roles*. Your edits are kept; only a missing default role is recreated.
- Check access with `rbac.check_access(request, "app_label.codename", obj)`. Models owned by an organization get checks for free through an `organization` foreign key.
- Nobody can grant or remove more than they hold. Every organization keeps at least one owner, and every member keeps at least one role.
- Implementation and the mapping from the standard's functions: `apps/orgs/rbac.py`, `apps/orgs/models.py`.

---

## Frontend Architecture

**Primary rendering: Django templates composed from [django-cotton](https://django-cotton.com) components + HTML forms.** Standard full-page loads for most interactions. Components live in `templates/cotton/` (`cotton/card.html` → `<c-card>`):

```html
<c-card title="New organization">
  <c-form>
    <c-fields :form="form" />
    <c-btn type="submit">Create</c-btn>
  </c-form>
</c-card>
```

**Navigation: htmx 4 boosts links inside the app shell.** Forms stay full page loads.

**Interactive islands: Stimulus mounts Svelte 5 components.** Pass server data with `json_script` and the generic bridge controller:

```html
{{ payload|json_script:"your-payload" }}
<div data-controller="svelte-bridge"
     data-svelte-bridge-component-value="area/YourComponent"
     data-svelte-bridge-props-id-value="your-payload">
</div>
```

Svelte components live in `frontend/src/js/svelte/` and are lazy-loaded via dynamic import. Only components on the page are downloaded.

**Animations: GSAP 3** for transitions and micro-interactions in both Stimulus controllers and Svelte components.

The rules for each layer (what goes where, Cotton conventions, hard rules) are in [AGENTS.md](AGENTS.md#frontend-formula).

---

## Services & Ports

| Service | Port | Notes |
|---------|------|-------|
| Django | `8000` | Main app |
| Vite HMR | `5173` | Dev only — proxied by django-vite |
| ClickStack | `8080` / `4317` / `4318` | `just dev` only: UI / OTLP gRPC / OTLP HTTP |

Only these are published. PostgreSQL stays internal to the compose network
(the app reaches it as `db:5432`), so a local Postgres on `5432` does not
clash and `just dev-psql` opens a shell (also as `make dev-psql`).

---

## Project Structure

```
django-starter-kit/
├── apps/
│   ├── core/          # BaseModel (UUID + timestamps) — keep lean
│   ├── users/         # User model (email login, avatar, auditlog)
│   ├── api/           # API endpoints (DMR)
│   ├── pages/         # Static/marketing pages, terms, privacy
│   ├── dashboard/     # Authenticated home
│   └── orgs/          # Organizations, RBAC roles (INCITS 359), email invitations
├── config/
│   ├── settings/
│   │   ├── base.py        # Shared config
│   │   ├── dev.py         # Development overrides
│   │   ├── production.py  # Production hardening
│   │   └── test.py        # Test isolation
│   ├── asgi.py            # ASGI entry point (+ OTEL init)
│   └── otel.py            # OpenTelemetry setup (opt-in)
├── frontend/
│   └── src/
│       ├── css/styles.css # Tailwind v4 + Basecoat
│       └── js/
│           ├── main.js                # Stimulus + GSAP bootstrap
│           └── controllers/           # Stimulus controllers (auto-registered)
├── templates/             # Django templates
│   └── cotton/            # Cotton components (<c-*>)
├── dev/                   # Docker dev environment
│   ├── Dockerfile
│   ├── docker-compose.dev.yml
│   ├── supervisord.conf
│   └── init.sh
├── justfile           # Task runner (Makefile mirrors it)
└── pyproject.toml         # All Python deps (managed by uv)
```

---

## Common Commands

```bash
# Dev environment (Docker)
just dev             # Start the stack (alias of dev-up)
just dev-slim        # Same, without analytics
just stop            # Stop the stack
just logs            # Follow logs
just bash            # Shell in the app container
just shell           # Django shell in the app container
just dev-clean       # Destroy containers + volumes (deletes the dev DB)

# Database
just makemigrations  # Generate migrations (host; files stay yours)
just migrate         # Apply migrations (in the app container)

# Quality
just lint            # ruff check
just lint-fix        # ruff check --fix
just format          # ruff format
just precommit       # all pre-commit hooks
just test            # pytest
```

`make <target>` works for the same names, except `precommit` (just only).

---

## Environment Variables

Copy `.env.example` to `.env`. It lists every key the settings read, with
comments. Real environment variables win over `.env`.

---

## Production Checklist

Before deploying:

1. **Set environment:** `ENVIRONMENT=production` + `DJANGO_SETTINGS_MODULE=config.settings.production`
2. **SSL/TLS:** Configure reverse proxy; then enable `SECURE_PROXY_SSL_HEADER`, `SECURE_SSL_REDIRECT`, and HSTS in `production.py`
3. **Static files:** built into the image (`just vite-build && just collectstatic`)
4. **Database:** migrations run on container start (`prod/init.sh`) under a Postgres advisory lock, so replicas never migrate concurrently
5. **Hosts:** set `ALLOWED_HOSTS`, keeping `localhost`: the container healthcheck calls `/healthz/` with `Host: localhost`
6. **Sentry:** Set `SENTRY_DSN` for error tracking
7. **Email:** Set `RESEND_API_KEY`, or `EMAIL_URL` for any SMTP server
8. **Legal:** replace the placeholder text in `templates/pages/terms.html` and `privacy.html`

### Production (Docker Swarm)

Build image and deploy stack:

```bash
export IMAGE_NAME=your-registry/django-starter-kit:latest
just stack-build
docker tag django-starter-kit $IMAGE_NAME
docker push $IMAGE_NAME
just stack-deploy
```

Required env vars:
- `SECRET_KEY` — Django secret
- `IMAGE_NAME` — Docker image for stack
- `POSTGRES_PASSWORD` — DB password
- `DEFAULT_FROM_EMAIL` — sender verified with your email provider
- `RESEND_API_KEY` or `EMAIL_URL` (`smtp+tls://user:pass@host:587`) — email delivery
- `CSRF_TRUSTED_ORIGINS` — public https origin(s), e.g. `https://example.com`
- `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_STORAGE_BUCKET_NAME` — external S3 bucket for media (optional `AWS_S3_ENDPOINT_URL` for non-AWS)

### Known Caveats

| Caveat | Detail |
|--------|--------|
| **Python 3.14** | Recent. Every current dependency ships wheels, so the images carry no compiler; add `build-essential` to the builder if one ever needs a source build. |
| **Root-owned files** | The dev container runs as root, so files it writes into the bind mount (e.g. `just makemigrations` via `just bash`) are root-owned on the host. `sudo chown -R $USER .` fixes it. |
| **DMR 0.x** | API framework pre-1.0. Pin version in `pyproject.toml` for stability. |
| **Granian** | Rust ASGI server — mature but smaller ecosystem than Gunicorn+Uvicorn. |
| **Postgres does it all** | Cache, sessions and the task queue live in Postgres — no Redis. Add a dedicated cache/broker only when load demands it. |

---

## Documentation

| Doc | Contents |
|-----|---------|
| [AGENTS.md](AGENTS.md) | Architecture, conventions, frontend formula, dev workflow (humans + agents) |
| [CHANGELOG.md](CHANGELOG.md) | Release changelog |

---

## License

MIT — see [LICENSE](LICENSE).
