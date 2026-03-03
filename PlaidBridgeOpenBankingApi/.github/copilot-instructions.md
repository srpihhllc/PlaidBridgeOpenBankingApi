# Copilot Instructions — Financial Powerhouse Platform

## Build, Test & Lint

All commands use `make` with a `venv/` virtualenv (pip-tools managed):

```bash
make dev          # Run Flask dev server (FLASK_ENV=development)
make test         # pytest with coverage (≥85% required)
make lint         # flake8 app/
make typecheck    # mypy app/
make format       # black + isort app/
make check        # lint + typecheck + test
make ci           # Full CI suite with XML coverage report
make migrate      # alembic upgrade head
make rollback     # alembic downgrade -1
make update       # Recompile requirements.lock + requirements-dev.lock
```

**Run a single test file:**
```bash
venv/bin/pytest app/tests/test_auth_routes.py
```

**Run tests by marker:**
```bash
venv/bin/pytest -m "auth"           # auth tests only
venv/bin/pytest -m "not redis"      # skip tests requiring live Redis
venv/bin/pytest -m "smoketest"      # quick lifecycle validation
```

Available markers: `auth`, `redis`, `plaid`, `providers`, `infra`, `migrations`, `smoketest`, `nightly`, `ci`.

**Mobile app** (in `mobile-app/`):
```bash
pnpm dev          # Expo + tRPC server concurrently
pnpm test         # vitest
pnpm check        # tsc --noEmit
pnpm lint         # expo lint
pnpm db:push      # drizzle-kit generate + migrate
```

Code style: **black + isort**, line-length **100**. Pre-commit hooks run black, flake8, isort, mypy, and a quick pytest on every commit.

---

## Architecture

This is a **unified fintech monorepo** with two independently deployable layers:

### Backend — Flask (`app/`)

Application factory pattern: `from app import create_app`. The top-level `flask_app.py` is a thin shim for legacy imports; don't use it for new code.

**Extension initialization** (`app/extensions.py`) — all Flask extensions (SQLAlchemy, JWT, LoginManager, SocketIO, Mail, CSRFProtect, Limiter) are module-level instances initialized once via `init_extensions(app)`. Import extensions from here, never re-instantiate them.

**Blueprint auto-discovery** (`app/blueprints/__init__.py`) — blueprints are auto-discovered via `pkgutil` with explicit ordering for critical routes (`pulse_bp`, `main_bp`, `api_bp`, `api_v1_bp`, `auth_bp`, `admin_bp`). Add new blueprints as files in `app/blueprints/`.

**Layer structure:**
- `app/models/` — SQLAlchemy models (all inherit from `db.Model`)
- `app/services/` — business logic (Plaid integration, PDF, fraud, MFA, etc.)
- `app/blueprints/` — Flask routes/blueprints
- `app/routes/` — additional route modules (cockpit, admin, API sub-packages)
- `app/decorators/` — `roles_required`, `admin_required`, `super_admin_required` (re-exported from `access.py`)
- `app/middleware/` — request ID injection, response wrapping
- `app/security/` — API key auth, request isolation
- `app/tests/` — all pytest tests (conftest.py provides `app`, `client`, `db_session` fixtures)

**Auth model** — dual-path: JWT (priority for API calls) with Flask-Login session fallback. `roles_required()` decorator handles both transparently. JWT `sub` claim is always an integer user ID. Token revocation uses `RevokedToken` model checked via `jwt.token_in_blocklist_loader`.

**Rate limiting** — `_NoopLimiter` is used automatically in `TESTING=True` or when `RATE_LIMIT_ENABLED=False`. Redis is used as backend when available; falls back to in-memory gracefully.

**Database** — SQLAlchemy with deterministic FK naming convention (defined in `extensions.py`). Migrations via Alembic (`migrations/`). Pool settings configurable via env vars (`SQLALCHEMY_POOL_SIZE`, `SQLALCHEMY_POOL_RECYCLE`, etc.).

### Mobile App — React Native / Expo (`mobile-app/`)

- **Expo Router** (file-based routing), React 19, React Native
- **tRPC** for type-safe API communication with the Express bridge server (`mobile-app/server/`)
- **Drizzle ORM** with MySQL2 for local/server DB
- **Biometric auth** via `expo-local-authentication`
- Package manager: **pnpm**

---

## Key Conventions

**SQLAlchemy naming convention** — all constraints use the deterministic convention from `extensions.py` (`ix_`, `uq_`, `fk_`, `pk_`, `ck_` prefixes). Alembic migrations must respect this or they will drift.

**Testing config** — tests use `create_app(env_name="testing")`. The `TestingConfig` sets `RATE_LIMIT_ENABLED=False` and `WTF_CSRF_ENABLED=False`. Do not override these in individual tests; let the config handle it.

**Lockfile discipline** — never edit `requirements.lock` or `requirements-dev.lock` by hand. Run `make update` after changing `requirements.txt` or `requirements-dev.txt`. Pre-commit will block commits if lockfile drift is detected.

**Environment variables** — copy `.env.example` and populate. Required: `DB_USER`, `DB_PASSWORD`, `DB_HOST`, `DB_NAME`. Optional Redis: `REDIS_URL`, `REDIS_STORAGE_URI`.

**Commit message format:**
```text
feat: short description
fix: short description
docs: short description
```

**Coverage gate** — pytest is configured with `--cov-fail-under=85`. PRs must maintain ≥85% coverage on `app/`.

**Blueprint naming** — blueprint variables follow `<name>_bp` convention (e.g. `auth_bp`, `api_v1_bp`). The auto-discovery system picks up any `Blueprint` instance at module level in `app/blueprints/`.
