# 🏗 Backend Architecture — Financial Powerhouse Platform

The backend is the core enforcement engine of the Financial Powerhouse Platform. It handles compliance, fraud detection, smart contract simulation, financial scoring, PDF ingestion, and open banking integrations.

---

## ⚙️ Technology Stack

- **Flask** — REST API framework  
- **SQLAlchemy ORM** — relational modeling  
- **Alembic** — schema migrations  
- **Redis** — rate limiting, telemetry, TTL traces  
- **JWT Authentication** — via flask‑jwt‑extended  
- **pdfplumber** — PDF statement parsing  
- **Plaid API** — account linking + transactions  
- **Treasury Prime** — banking operations  

---

## 🧩 High‑Level Architecture

Client → Flask API → Services → SQLAlchemy → PostgreSQL  
└── Redis (rate limits, telemetry)

Notes:
- Keep business logic in services (thin controllers / route handlers).
- Background workers (e.g., PDF parsing, contract simulation) should be separate processes and communicate via a job queue (Redis/RQ, Celery, or similar).

---

## 📂 Directory Structure

app/
├── __init__.py
├── config.py
├── models.py
├── routes/
├── services/
├── migrations/
└── tests/

Suggested additions:
- app/services/workers.py (worker registration and job handlers)
- app/utils/monitoring.py (health checks / telemetry helpers)
- app/schemas/ (Pydantic or marshmallow schemas if used)

---

## 🚦 Core Responsibilities

### Compliance Engine
- AI‑driven agreement scanning  
- Auto‑lock on repeated violations

### Fraud Detection
- Transaction anomaly detection  
- Auto‑lock on suspicious activity

### Smart Contract Simulation
- Deterministic execution  
- Event‑driven state transitions

### Financial Health Scoring
- Transaction‑based scoring  
- Risk modeling

### Open Banking
- Plaid OAuth  
- Transaction ingestion  
- PDF → transaction extraction

---

## 🔐 Security Model

- JWT authentication (access + refresh patterns)
- SECRET_KEY and JWT keys rotated per policy
- Rate limiting via Redis with safe failover
- Admin seed validation covered by CI smoke tests
- Strict FK integrity and DB constraints

Security notes:
- Never commit secrets (use environment variables or a secrets manager).
- Add automated secret scanning in CI (git-secrets, truffleHog, or similar).
- Consider short-lived service tokens and RBAC scopes for internal services.

---

## 🧪 Testing Strategy

- Enforce high coverage for critical components (compliance, fraud rules).
- CI smoke tests validate:
  - admin seed presence and correctness
  - key FK relationships and cross-table integrity
  - migration sanity checks (Alembic)
- Unit tests for deterministic logic (scoring, contract simulation)
- Integration tests for external integrations (Plaid, Treasury Prime) using sandbox credentials or recorded fixtures

---

## 📡 Telemetry & Observability

- Redis TTL traces and rate‑limit counters
- /health endpoint for liveness/readiness
- Audit logs for compliance and fraud events
- Instrument critical flows (agreement scans, account linking, contract runs) with traces and metrics
- Ensure logs include correlation IDs to follow a request across services

---

## Operational / Maintenance Notes

- Prefer additive, backward-compatible DB migrations (add columns → backfill → switch → drop)
- Run alembic revision + tests in CI to ensure migrations are runnable
- Document runbooks for long-running jobs (PDF parsing, contract simulation)
- Use feature flags for risky changes to compliance/fraud logic

---

## How to update this document
1. Edit docs/03-backend-architecture.md with structural changes.
2. If you change architecture or add major services, include an updated diagram (docs/images/backend-architecture.png or .svg).
3. Include a short note in the PR describing operational implications (migrations, secrets, rollout plan).

---
