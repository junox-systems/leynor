# AGENTS.md — Django Starter Kit

Django 5.2 LTS starter kit. Modular monolith. Lean, opinionated, prod-ready. Single source of truth for architecture + conventions.

## Principles

- Let packages do their job: thin integration over custom abstraction (allauth, auditlog, DMR, django-q2).
- Fat models, thin views. Logic in models/managers/service functions.
- YAGNI: no tuning for hypothetical scale. Add soft-delete (`django-safedelete`), search managers, view caching only when needed.
- Modern, maintained packages only.

## Stack

| Area | Choice |
|---|---|
| Backend | Django 5.2, Python 3.14+, Granian ASGI (`granian[uvloop]`), Whitenoise static |
| DB | ParadeDB = Postgres 18 + `pg_search` BM25 + pgvector, via `django-paradedb`. Also cache (`DatabaseCache`), sessions, task queue. **No Redis** |
| Tasks | django-q2, ORM broker (`Q_CLUSTER["orm"]`) |
| Auth | django-allauth: local, email verify, OIDC/SSO, social (Google, Apple, Microsoft), MFA |
| API | django-modern-rest (DMR) 0.x + msgspec. **Not DRF** |
| Frontend | Django templates from **django-cotton** components + Django forms → htmx 4 (boosted nav, app shell only) → Stimulus 3 mounts Svelte 5 islands → GSAP 3 |
| Styling | Tailwind v4 + Basecoat (shadcn tokens, per-site `site.css` pack, fork of `basecoat-css/styles/vega`). Fonts: Manrope body, Space Grotesk headings (Fontsource) |
| Build | Vite (`django-vite`), uv, pnpm (Node 24), just (+ mirror `Makefile`), Docker Debian trixie-slim |
| Config | `django-environ` (`env.db()`, `env.bool()`); all vars in `.env.example` |
| Storage | `django-storages` behind one Storage API: local FS by default, `s3`/`azure`/`gcs` via `STORAGE_BACKEND` (complete `AWS_*` selects s3). `django-imagekit` avatar thumbs |
| Email | Resend (`django-anymail`) if `RESEND_API_KEY`, else any SMTP via `EMAIL_URL` |
| Admin | stock admin + dj-control-room (cache, urls, signals panels), constance, import_export, auditlog |
| Observability | Sentry (if `SENTRY_DSN`; 10% traces, no PII). OTEL opt-in `OTEL_ENABLED=true`: Django + psycopg only, any OTLP backend |
| Tooling | ruff, pytest, django-debug-toolbar (`/__debug__/`) |

## Layout

```
apps/           # ALL backend code. Never at project root
  core/         # BaseModel, cache-table migration, tasks.retry — keep lean
  users/        # User (email login, UUID PK, avatar)
  api/          # DMR controllers + schemas/
  pages/        # static/marketing pages
  dashboard/    # /dashboard/ — panel payloads, no models
  orgs/         # orgs, memberships, RBAC roles (rbac.py), email invitations
config/
  settings/     # base / dev / production / test
  asgi.py       # ASGI + OTEL init
  otel.py
frontend/src/
  css/styles.css  # Tailwind + Basecoat base + @source globs
  css/site.css    # Basecoat style pack — all component visuals
  js/main.js      # htmx config, Stimulus boot, controller auto-register
  js/controllers/ # Stimulus (auto-registered)
  js/svelte/      # islands: app/ (Sidebar), dashboard/
templates/
  base.html       # public pages
  base_app.html   # authed app shell (htmx-boosted)
  cotton/         # Cotton components; icon/ = one SVG per file
  <app>/          # pages
dev/            # Docker dev env (Dockerfile, compose, supervisord)
```

## Backend

### Apps
- Each app: `__init__.py`, `apps.py`, `models.py`, `admin.py`, `views.py`, `tests/`.
- `core` = only truly universal code. Domain grows → own app.

### Models
- All inherit `apps.core.models.BaseModel`: UUID v7 `id`, `created_at`, `updated_at`.
- Register change tracking: `auditlog.register(MyModel)` → `/admin/auditlog/`, `MyModel.history`.
- `User`: `USERNAME_FIELD = "email"`, UUID PK, `avatar` + `avatar_thumbnail` (imagekit 100×100 JPEG), `AbstractUser` fields. No `UserProfile` — fields live on `User`.
- **Never add OIDC/social fields to `User`** — allauth `SocialAccount` holds them.
- Querysets: `select_related` (FK/1:1), `prefetch_related` (M2M/reverse). No N+1.
- Search: `django-paradedb` (`ParadeDBIndex`, lookups) or raw SQL at service/view layer.
- Cache: `django.core.cache.cache` / `@cache_page` only where measured slow. Table from `core` migration `0001_create_cache_table`.

### Settings
- Pick via `DJANGO_SETTINGS_MODULE`. `settings/__init__.py` empty — no routing.
- `dev` (default in `manage.py`/`asgi.py`; warns if `ENVIRONMENT=production`), `production`, `test` (set in `pyproject.toml`).
- `production.py` / `dev.py` / `test.py` = `from .base import *` + overrides. **Never change this pattern.**
- SSL/HSTS commented out. **Never auto-enable** — manual per deploy topology.
- Templates: loaders listed by hand (Cotton). `base.py` cached, `dev.py` uncached for hot reload.

### API (DMR)
- Controllers `apps/api/views.py`, schemas `apps/api/schemas/<name>.py`.
- `dmr.Controller` + `MsgspecSerializer`. Session auth.
- Response validation ON dev, OFF prod (`production.py`).

### Tasks (django-q2)
```python
# apps/myapp/tasks.py — plain function
def send_welcome_email(user_id: str): ...

from django_q.tasks import async_task
async_task("apps.myapp.tasks.send_welcome_email", str(user.id))
```
- Failed task not re-queued → wrap with `apps.core.tasks.retry` for backoff.
- Results/failures/schedules: admin → *Django Q*. Tests run inline (`"sync": True`).

### Orgs & RBAC
Modeled on **ANSI INCITS 359-2004**, *Information Technology – Role Based Access Control* (Core + Limited Role Hierarchies; superseded by INCITS 359-2012 (R2022)). Text: https://www.cs.purdue.edu/homes/ninghui/readings/AccessControl/ANSI+INCITS+359-2004.pdf · NIST: https://csrc.nist.gov/projects/role-based-access-control. Design reference, not a compliance claim.

| Standard | Here |
|---|---|
| USERS / ROLES | `User` / `orgs.Role` (global rows, admin-editable) |
| OPS × OBS = PRMS | Django `Permission` (codename × content type), objects scoped to one org |
| UA | `Membership.roles` (per organization) |
| PA | `Role.permissions` |
| RH (limited) | `Role.descendant`: one immediate junior, inherits its perms, acyclic |
| SESSIONS | Django session key `rbac` = membership + dropped roles; active = authorized − dropped |

- Functional spec = `apps/orgs/rbac.py`, one function per standard function (`assign_user`, `check_access`, `add_inheritance`, …). Change roles/assignments through it, never raw `.roles.add()` in views.
- Access check: `rbac.check_access(request, "app.codename", obj)`. Org-owned model → `organization` FK; check resolves through it, denies other orgs.
- Org pages call `rbac.activate(request, membership)`: viewing an org makes it the session org. App bar switcher → `org_switch`.
- Delegated admin (our policy, not 359): `can_administer_role` / `can_manage_member` — no one grants or removes more than they hold. Under `Organization.lock()`: last owner keeps owner, every member keeps ≥1 role. Org pages need `orgs.view_organization`.
- Defaults owner ⊇ admin ⊇ member: created + granted by migration `orgs 0002`; `post_migrate` (`seed_default_roles`) recreates only missing ones (test DBs, deleted defaults). Existing roles never touched — operator edits survive.
- Role assigned mid-session = active next request; deassigned = gone next request. No re-login needed.
- Signup → personal org (`signals.py`). Users can still have zero orgs (admin-created, left all) → `current_session()` is `None` → empty state.
- New org-level operation = add to `Organization.Meta.permissions` + grant in `DEFAULT_ROLES`. No per-org custom roles or SSD/DSD yet (YAGNI).
- No django-guardian. Per-object grants for one user only if a real need appears.

## Frontend Formula

Django renders pages from Cotton components. Svelte renders interactive parts. Stimulus = only bridge between them. Read before touching `templates/` or `frontend/src/js/`.

### Who owns what

| Layer | Owns | Never |
|---|---|---|
| Django view | fetch + authorize data, shape to JSON-safe primitives | HTML for an island; model objects in payloads |
| Django template | page structure, layout, **every URL**, mount points, `json_script` | client state, business logic, markup a component owns |
| Cotton component (`templates/cotton/`) | reusable server markup: Basecoat primitives, chrome, icons | query data, resolve URLs, hold state |
| Stimulus controller | DOM lifecycle, browser APIs (`matchMedia`, `localStorage`, doc listeners), mounting islands | render UI, hold app state |
| Svelte component | interactive UI + client state | resolve URLs, render nav/chrome, fetch on mount |
| Basecoat CSS (`site.css`) | all visuals | — no component CSS |
| DMR (`apps/api`) | refresh + mutation endpoints | duplicate view's data shaping |

**URLs = Django, always.** `reverse()` / `{% url %}`, passed down as data. Hardcoded path in `.svelte` = bug.

### Lightest layer wins

Stop at first rung that holds:
1. Static content → template of Cotton components. No JS.
2. Form → Django form in `<c-form>` + `<c-fields>`, full page load. Default for all input.
3. DOM behavior, no state (toggle, drawer, keys, browser API) → Stimulus (`controllers/sidebar.js`, `theme-toggle.js`).
4. Reactive UI w/ client state → Svelte island via `svelte-bridge`.
5. Must survive navigation → island + `hx-preserve` + unique `id` (`svelte/app/Sidebar.svelte`).

Rung 4 costs a chunk, a mount, a data contract. Rungs 1–3 free.

### Where things go

| What | Where |
|---|---|
| Data shaping (one fn per unit) | `apps/<app>/panels.py` |
| Cross-page shell data | `apps/<app>/context_processors.py` (register in `TEMPLATES`) |
| Routes | `apps/<app>/urls.py`, no `app_name` (root namespace) |
| Page | `templates/<app>/<page>.html` |
| Reusable markup / chrome | `templates/cotton/<name>.html` → `<c-name>` |
| Icon | `templates/cotton/icon/<name>.html` → `<c-icon.name />` |
| Layouts | `templates/base.html`, `templates/base_app.html` |
| Stimulus | `frontend/src/js/controllers/<name>.js` |
| Svelte | `frontend/src/js/svelte/<area>/<Name>.svelte` |
| API | `apps/api/views.py` + `apps/api/schemas/<name>.py` |

Naming: `foo-bar.js` → `data-controller="foo-bar"`; `admin/table.js` → `admin--table`. Svelte value = path under `svelte/` sans ext: `app/Sidebar`. Cotton file snake_case, tag kebab-case: `cotton/theme_toggle.html` → `<c-theme-toggle>`; subdir → dot: `icon/panel_left.html` → `<c-icon.panel-left />`.

### Layouts

- `base.html` — public. Blocks: `title`, `extra_head`, `header`, `body`, `content`, `footer`, `extra_body`. Holds pre-paint inline script (theme + transition suppression) — **keep plain blocking `<script>`**; `main.js` is deferred module, runs after paint. Loads assets: `{% vite_hmr_client %}` + `{% vite_asset 'src/js/main.js' %}`.
- `base_app.html` — **every authed page.** App bar + sidebar mount; blanks `header`/`footer`. Pages set `{% block page_title %}`.
- New authed route = extend `base_app.html`. Nothing else.
- Dark mode = `.dark` on `<html>`, toggled by `theme-toggle` controller.

### Cotton components

All server markup built from `templates/cotton/`. Pages compose; never repeat Basecoat markup by hand.

| Component | Use |
|---|---|
| `<c-card title description lead body_class>` | every card. `lead` = page heading (h2). Slots: default = body, `header` = replaces header, `actions` = footer |
| `<c-btn href variant size>` | every button / button-link. `href` → `<a>` |
| `<c-badge variant>` | badges |
| `<c-alert variant>` | alerts. `destructive` → `role="alert"`, else `role="status"` |
| `<c-form>` | every POST form. CSRF built in; `action`/`id`/`data-*` pass through |
| `<c-fields :form="form" />` | whole Django form (non-field errors + each field) |
| `<c-field for label help errors>` | one hand-built control; control in slot |
| `<c-center class="max-w-md">` | centered logged-out page (auth) |
| `<c-avatar src alt initial size>` | avatar image or initials fallback. `size` = `sm` / `lg` |
| `<c-messages>` | Django messages → Basecoat toasts. Once, end of `base.html`. Never `toaster.toast()` with server data — unescaped |
| `<c-header>` `<c-footer>` `<c-theme-toggle>` `<c-icon.*>` | chrome |

```html
<c-card title="New organization">
  <c-form>
    <c-fields :form="form" />
    <c-btn type="submit">Create</c-btn>
  </c-form>
</c-card>
```

New component skeleton:
```html
<c-vars label value class />
<div class="card{% if class %} {{ class }}{% endif %}" {{ attrs }}>
  <section class="p-5">{{ label }}: {{ value }}</section>
</div>
```

Rules:
1. One component, one job. New one only if markup repeats (2+) or is chrome. One div of utilities ≠ component.
2. Reuse first: `<c-btn>` not `<button class="btn">`, `<c-card>` not `<div class="card">`. `{% include %}` only for third-party (allauth) snippets, never our markup.
3. Props in `<c-vars>`; rest flows via `{{ attrs }}` (`type`, `name`, `hx-*`, `data-*`, `aria-*`). Append to `class`, never replace base class.
4. `title="Hi {{ x }}"` = string, escaped once. `:form="form"` = Python object. Raw `&` in attrs — `&amp;` double-escapes.
5. Full class names only. Never `max-w-{{ size }}` — Tailwind purges it. Pass `class="max-w-md"`.
6. Pass data explicitly. Exception: chrome (`header`, `messages`, `form`) reads request context `user`, `messages`, `csrf_token`.
7. Never write `<c-` in a comment — Cotton compiles inside comments.
8. `{% block %}` inside a component tag is overridable — layouts may wrap blocks in components.
9. htmx passes through unchanged: `hx-*` via `{{ attrs }}`; `<c-form>` renders plain `<form>`, so `main.js` keeps it native.
10. Loaders by hand (`django_cotton.apps.SimpleAppConfig`): keep `django_cotton.cotton_loader.Loader` first in `base.py` + `dev.py`. Auto config would clobber dev's uncached loaders.
11. `templates/allauth/elements/*` adapt allauth → our components. `button.html`, `field.html` stay raw: allauth optional attrs would render empty (`form=""` detaches button from form).
12. Cotton = static server markup. Needs client state → Svelte island. Never build same job in both.

### Data flow (islands)

One direction, one shape. Server owns shape.

```
view.get_context_data()          →  dict of primitives (no model objects, no datetimes-as-objects)
  ↓ {{ payload|json_script:"x" }}
template                         →  <script type="application/json" id="x">
  ↓ data-svelte-bridge-props-id-value="x"
svelte-bridge (Stimulus)         →  JSON.parse, mount()
  ↓
Component                        →  let { ... } = $props()
```

Live refresh: island fetches DMR endpoint calling **same payload fn** → shapes can't drift.

```
Component  →  fetch(urls.thing, {credentials: "same-origin"})  →  DMR controller  →  thing_payload(user)
                                                                       ↑
view.get_context_data() ───────────────────────────────────────────────┘
```

- Endpoint URLs ride in payload: `"urls": {"thing": reverse("thing")}`.
- Props read once at mount, not reactive (no `propsValueChanged`). Change after mount = `$state` or fetch.
- `data-svelte-bridge-props-value='{...}'` only for hand-written constants. Server data → `json_script`.
- Bridge lazy-imports component (own chunk), mounts, unmounts on disconnect. Dedicated controller with static `import` + `mount()`/`unmount()` only when extra lifecycle needed — ships in main bundle. Ref: `controllers/svelte-bridge.js`.

### Recipe: interactive unit

1. `<name>_payload(user) -> dict` in `apps/<app>/panels.py`. JSON-safe primitives.
2. Add key to view's `payload` in `get_context_data`.
3. Template: `{{ payload|json_script:"<id>" }}` + mount el: `data-controller="svelte-bridge"`, component value, `data-svelte-bridge-props-id-value="<id>"`.
4. `svelte/<area>/<Name>.svelte`, runes only (`$props`, `$state`, `$derived`). Card chrome: reuse `dashboard/Panel.svelte`.
5. Live refresh only: DMR controller calling same `*_payload`; URL via payload.
6. Verify: `just test` → `cd frontend && pnpm run build` → load page, check console. `svelte-bridge: no component found` = wrong component path.

Dashboard: `svelte/dashboard/Dashboard.svelte` = one root composing panels. Root owns layout + cross-panel state; children get props + callbacks, **never own stores/context**. New panel = render in root grid with its slice.

### htmx (boosted nav)

- htmx 4, app shell only: `base_app.html` sets `hx-boost:inherited="true"` (v4 inheritance explicit). Public pages plain loads. Opt out one link: `hx-boost="false"`.
- Boosted response swaps `<body>`, keeps only new `<title>` → every boosted page shares `base.html` head assets.
- Forms native: `main.js` cancels `htmx:before:init` for forms that only inherited boost. Form with own `hx-post` left alone.
- Island-rendered links miss htmx's scan → `svelte-bridge` calls `htmx.process()` after mount.
- Persistent island: unique `id` + `hx-preserve`. Bridge **adopts** existing instance, defers teardown one tick ("moving" vs "gone"). Remove → blink every visit or leaked listeners.
- Preserved island can't re-render from server HTML → page-dependent state (active nav) from `location.pathname` on `htmx:after:history:push` + `popstate`.

### Hard rules (each already caused a real bug)

1. `.svelte` line in `@source` (`frontend/src/css/styles.css`) **stays**. Gone → Svelte-only classes purged in prod, no warning. Verify: grep `dist/assets/main-*.css` for Svelte-only class.
2. `{# #}` single-line only. Multi-line leaks as text → closes `<head>` early. Use `{% comment %}`. `{% extends %}` must be first tag.
3. Never hand-build JSON into HTML attr (`&quot;`, apostrophes break quoting, injection). Use `json_script`.
4. No secrets / raw audit values in payloads. `LogEntry.changes` holds password hashes; `activity_payload` sends field *names* only.
5. Islands fetch GET only. No CSRF token exposed to JS yet → POST needs that solved first.
6. Icon *names* through JSON, not markup. Components map names from closed constant table.
7. Pre-first-paint behavior = blocking inline script in `base.html`, never Stimulus.
8. No component CSS. Basecoat styles `.card`, `.sidebar`, `.alert`, `.empty`, `.btn`, `.field`… via class + `data-*` (`class="btn" data-variant="outline" data-size="sm"`), used through Cotton components. Respect structure: `.sidebar + *` applies content margin → content wrapper stays sidebar's immediate next sibling.
9. htmx = navigation only. Interactive UI = Svelte island. **Turbo removed — never add back.**
10. Empty states = default view on fresh install. Build as real states.

### Smells

- `fetch` that could be a prop → move to view.
- Hardcoded `/path/` in `.svelte` → resolve in Django.
- New `.css` file / `<style>` reimplementing Basecoat → delete.
- Svelte rendering nav/chrome → Django's job.
- `class="btn|card|alert|badge"` or `{% csrf_token %}` in a page → Cotton component.
- `{% include "_partial.html" %}` of our markup → Cotton component.
- Two payload shapes for same data → share one fn.
- Store / `setContext` between islands → one root owns state, or merge islands.

## Critical rules

1. Never change settings inheritance (`from .base import *` split).
2. Never add OIDC fields to `User`.
3. Never add Turbo back.
4. Never put backend code outside `apps/`.
5. Never tune caching/auditlog for hypothetical scale.
6. Never auto-enable SSL/HSTS.
7. Never let Svelte own URLs, navigation, page chrome.
8. Never let htmx boost forms by inheritance (`main.js` enforces).
9. Never hand-write Basecoat markup in page templates — compose `templates/cotton/`.

## Dev

Docker (`dev/docker-compose.dev.yml`): `db` = `paradedb/paradedb:0.26.2-pg18`; `app` = Django + Vite + qcluster under supervisord (waits db health → deps → migrate); `clickstack` = OTEL UI `:8080` (`just dev` only). Media local in dev, S3 in prod.

```bash
just dev            # all services (alias dev-up); just dev-slim = no analytics
just stop | logs | restart | bash | shell
just dev-clean      # drop volumes — deletes dev DB
just dev-psql       # psql in the db container (no host port is published)
just django-dev | vite-dev | qcluster-dev  # what supervisord runs inside `app`
just vite-build     # prod assets → frontend/dist/ (Whitenoise serves)
just make / migrate # makemigrations / migrate
```

Deps: `uv add|remove <pkg>`, `uv sync`; JS `cd frontend && pnpm add|remove <pkg>`.

## Testing & CI

- `just test` → pytest, `config.settings.test`. Tests per app in `apps/<name>/tests/`. Warnings are errors (`filterwarnings` in `pyproject.toml`).
- `just test-assets` → the build assertions in `apps/core/tests/test_frontend.py`; needs `frontend/dist`, so run after `just vite-build`.
- `just e2e` → browser tests vs built assets (`-m e2e`).
- `just check-deploy` → `check --deploy --fail-level WARNING` on production settings. Silenced in `production.py`: TLS W004/W008 (SSL/HSTS stay opt-in) and the Vite/staticfiles warnings that only report missing build output, since the check runs on a clean tree; any other warning fails.
- `just smoke-prod` → boot built prod image (db + web + qcluster via `prod/smoke.sh`), probe health, pages, static, OpenAPI.
- `apps/core/tests/test_cotton.py` fails if a `<c-` tag reaches the browser. `test_templates.py` compiles every template and rejects multi-line `{# #}`.
- CI (`.github/workflows/ci.yml`, push/PR to `main`): `just install` → `lint` → `check-deploy` → `test` → `vite-build` → `test-assets` → `docker-build` → `smoke-prod`.
