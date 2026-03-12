# 🧭 Developer Onboarding — Financial Powerhouse Platform

Welcome to the Financial Powerhouse Platform. This guide provides a complete onboarding path for backend, mobile, and full‑stack engineers.

---

## 1. Prerequisites

### Backend
- Python 3.11+
- Poetry
- PostgreSQL 14+
- Redis 6+
- Plaid sandbox credentials
- Treasury Prime sandbox credentials

### Mobile
- Node 18+
- pnpm 9+
- Expo CLI
- Watchman (macOS)

---

## 2. Clone & Initialize the Repository

```bash
git clone https://github.com/srpihhllc/PlaidBridgeOpenBankingApi.git
cd PlaidBridgeOpenBankingApi
```

---

## 3. Backend Setup

Install dependencies, run migrations and start the dev server:

```bash
poetry install
poetry run alembic upgrade head
poetry run flask run
```

Environment variables (.env or your environment manager):

```env
# .env.example (DO NOT commit secrets)
SQLALCHEMY_DATABASE_URI=postgresql://user:pass@localhost:5432/dbname
REDIS_URL=redis://localhost:6379
JWT_SECRET_KEY=your_jwt_secret
SECRET_KEY=your_flask_secret
PLAID_CLIENT_ID=...
PLAID_SECRET=...
TREASURYPRIME_API_KEY=...
```

Note: Use a secrets manager for production. Ensure `.env.example` contains placeholders only.

---

## 4. Mobile App Setup

```bash
cd mobile-app
pnpm install
pnpm start
```

Environment variables for the mobile app are loaded via:
- mobile-app/scripts/load-env.js (or your shell/CI secrets manager)

---

## 5. TRPC Server

The TRPC server lives in `server/` and runs with the mobile app in development.

Key files:
- `server/_core/trpc.ts`
- `server/_core/context.ts`
- `server/_core/oauth.ts`
- `server/routers/*`

---

## 6. Database Migrations

Backend (Alembic):

```bash
poetry run alembic revision -m "describe change"
poetry run alembic upgrade head
```

Mobile (Drizzle):

```bash
cd mobile-app
pnpm drizzle:generate
pnpm drizzle:migrate
```

Best practice: prefer additive, backward-compatible migrations (add columns, backfill, switch code, then drop legacy columns).

---

## 7. Testing

Backend:

```bash
poetry run pytest --cov=app
```

Mobile:

```bash
cd mobile-app
pnpm test
```

CI should run tests and require coverage thresholds as configured.

---

## 8. Security Expectations

- No secrets in source control; use `.gitignore` and a secrets manager.
- Rotate JWT keys and `SECRET_KEY` regularly.
- Admin seed password must be changed in production.
- OAuth secrets handled server-side.
- Redis must be secured in production (VPC, auth, firewall rules).

---

## 9. Operator Expectations

- Run migrations before each deploy.
- Validate admin seed via CI smoke tests.
- Monitor Redis telemetry and rate-limit metrics.
- Review fraud/compliance logs regularly.
- Validate Plaid/Treasury Prime connectivity after deployments.

---

## Quick Links & Tips
- For a visual ERD export, add `docs/images/database-erd.png` and reference it in `docs/04-database-erd.md`.
- Keep onboarding steps in sync with `mkdocs.yml` nav.

---

Congratulations — you should now be set up to develop and run the platform locally.
