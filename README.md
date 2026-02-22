# 📘 Financial Powerhouse API

This module contains the core Flask application for the **Financial Powerhouse API**. It enforces ethical lending, fraud detection, smart contract automation, real‑time financial health monitoring, and open banking integration.

[![CI Tests](https://github.com/srpihhllc/PlaidBridgeOpenBankingApi/actions/workflows/tests.yml/badge.svg)](../../actions/workflows/tests.yml)

---

## 🏗 Architecture Overview
- **Framework**: Flask
- **Database**: SQLAlchemy ORM + Alembic migrations
- **Authentication**: JWT (via `flask-jwt-extended`)
- **Rate Limiting**: `flask-limiter`
- **Logging**: Python logging with configurable log level
- **Integrations**:
  - Plaid (account linking, transactions)
  - Redis (telemetry, rate limiting, TTL traces)
  - Treasury Prime (sandbox/production APIs)
  - PDF parsing (via `pdfplumber`)

---

## 📂 Key Files & Directories
- `__init__.py` → App initialization and extension setup
- `config.py` → Environment‑driven configuration (Flask secrets, DB, Redis, email)
- `models.py` → SQLAlchemy models (`User`, `LoanAgreement`, `Transaction`, etc.)
- `routes/` → API endpoints grouped by domain (compliance, fraud, accounts, etc.)
- `services/` → Business logic (AI compliance, fraud detection, scoring)
- `migrations/` → Alembic migration scripts (baseline + upgrades/downgrades)
- `app/tests/` → Pytest suite (unit tests, FK smoke‑tests, CI coverage)

---

## 🚦 Core Endpoints

| Endpoint                  | Method | Purpose                                      |
|----------------------------|--------|----------------------------------------------|
| `/review_agreement`        | POST   | AI compliance scan of loan terms             |
| `/compliance_report`       | GET    | Generate compliance report                   |
| `/validate_transaction`    | POST   | Fraud detection                              |
| `/link_borrower_account`   | POST   | Secure borrower account linking              |
| `/unlink_borrower_account` | POST   | Prevent unlinking if obligations remain      |
| `/upload_statement`        | POST   | PDF parsing and transaction extraction       |
| `/generate_link_token`     | GET    | Plaid Link token generation                  |
| `/execute_contract/<id>`   | POST   | Simulated smart contract execution           |
| `/financial_health/<id>`   | GET    | Real‑time financial health score             |
| `/convert_currency`        | POST   | Currency conversion                          |
| `/biometric_auth`          | POST   | Placeholder biometric authentication         |
| `/health`                  | GET    | Health check (operator visibility)           |

---

## 🔐 Security & Configuration
- **Secrets**: Loaded from environment variables (`.env` in dev, injected in prod).
- **JWT & SECRET_KEY**: Must be rotated regularly.
- **Rate Limiting**: Enabled globally to prevent abuse.
- **Redis**: Defaults to `localhost:6379` for local dev.
- **Flask App**: Defaults to `localhost:5000` (configurable via `PORT`).

### Key Environment Variables
| Variable                  | Purpose                                |
|----------------------------|----------------------------------------|
| `SQLALCHEMY_DATABASE_URI` | SQLAlchemy connection string           |
| `REDIS_URL`               | Redis connection string                |
| `JWT_SECRET_KEY`          | Secret for JWT signing                 |
| `SECRET_KEY`              | Flask session secret                   |
| `MAIL_SERVER`             | Outbound email server                  |
| `PORT`                    | Port for Flask app (default: 5000)     |

---

## 🔧 Database Migrations
We use **Alembic** for schema migrations.

```bash
# Create a new migration
poetry run alembic revision -m "describe change"

# Apply migrations
poetry run alembic upgrade head

# Roll back
poetry run alembic downgrade -1
```

- The baseline migration seeds an **admin user** (`admin@example.com` / `ChangeMe123!`) with a reproducible scrypt hash.
- Downgrades automatically remove the seeded admin before dropping tables.
- All foreign keys are validated by parametrized pytest smoke‑tests.

---

## 🧪 Running Tests

```bash
# Run all tests with coverage
poetry run pytest --cov=app

# Run only fast commit‑time tests
poetry run pytest -m ci

# Run provider‑specific tests
poetry run pytest -m plaid
poetry run pytest -m treasuryprime

# Run nightly soak/stress tests
poetry run pytest -m nightly
```

- **Coverage**: Enforced at **100%** via `pytest-cov`. Builds fail if coverage dips.
- **Smoke‑tests**: `app/tests/test_baseline.py` validates:
  - Admin user exists.
  - All 27 child tables referencing `users` enforce FK integrity.
  - Cross‑table FKs (bank_transactions, ledger_entries, subscriptions, complaint_logs, fraud_reports) are enforced.

---

## 📊 Telemetry & Observability
- **Redis**: Stores rate‑limit counters, TTL traces, and operator telemetry.
- **Health Checks**: `/health` endpoint exposes liveness and readiness.
- **Audit Trails**: All critical actions (migrations, fraud flags, compliance locks) are logged with timestamps.
- **CI/CD**: GitHub Actions runs migrations, seeds DB, executes full test suite, and enforces coverage.

---

## 🛡️ Operational Behavior
- **Compliance**: Loan agreements flagged 3+ times auto‑lock borrower accounts.
- **Fraud**: Suspicious transactions auto‑lock accounts immediately.
- **Contracts**: Smart contracts are simulated but structured for blockchain integration.
- **Health**: `/health` endpoint ensures operator visibility.
- **Telemetry**: Latency traces and TTL telemetry are emitted to Redis and validated by property‑based tests.

---

## 🧭 Operator Checklist
For new operators or deployments:

1. **Migrate DB**
   ```bash
   poetry run alembic upgrade head
   ```
2. **Verify Admin Seed**
   ```sql
   SELECT id, username, email, role, is_admin FROM users WHERE email='admin@example.com';
   ```
3. **Run Smoke‑Tests**
   ```bash
   poetry run pytest app/tests/test_baseline.py
   ```
4. **Rotate Secrets**
   - Change `JWT_SECRET_KEY` and `SECRET_KEY` immediately in production.
   - Rotate the seeded admin password.
5. **Monitor Telemetry**
   - Check Redis traces and `/health` endpoint.
   - Review logs for compliance/fraud auto‑locks.

---

## 🚀 Quickstart

```bash
# Install dependencies
poetry install

# Run the app locally
poetry run flask run
```

---

This README now provides **architecture, migrations, testing, telemetry, and operator guidance** in one cockpit‑grade document.

---
