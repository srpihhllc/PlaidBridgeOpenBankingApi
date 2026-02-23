📘 Financial Powerhouse Platform — Unified Architecture
A full‑stack, operator‑grade fintech platform combining:

Flask Backend API (compliance, fraud, contracts, telemetry)

React Native / Expo Mobile Banking App

Shared TypeScript TRPC Server

Drizzle ORM Schema + Migrations

Unified Developer Workflows

Cockpit‑Grade Operator Visibility

This repository represents the entire banking system in one cohesive, maintainable, operator‑friendly monorepo.

🏗️ High‑Level Architecture
Code
┌──────────────────────────────────────────────┐
│              Mobile App (Expo)               │
│  React Native UI • Screens • Hooks • UX Flow │
└───────────────────────┬──────────────────────┘
                        │ TRPC Calls
┌───────────────────────▼──────────────────────┐
│        Shared TypeScript Server (TRPC)       │
│ Routers • OAuth • Notifications • LLM • Auth │
└───────────────────────┬──────────────────────┘
                        │ REST / JSON
┌───────────────────────▼──────────────────────┐
│              Flask Backend API               │
│ Compliance • Fraud • Contracts • Telemetry   │
└───────────────────────┬──────────────────────┘
                        │ SQLAlchemy ORM
┌───────────────────────▼──────────────────────┐
│                 PostgreSQL DB                │
│     Alembic + Drizzle Schema + Migrations    │
└──────────────────────────────────────────────┘
📂 Repository Structure
Code
PlaidBridgeOpenBankingApi/
│
├── app/                         # Flask backend API
│   ├── models.py
│   ├── routes/
│   ├── services/
│   ├── tests/
│   ├── migrations/
│   └── config.py
│
├── mobile-app/                  # React Native / Expo mobile app
│   ├── app/                     # Screens + navigation
│   ├── assets/                  # Images, icons, splash
│   ├── components/              # UI components
│   ├── hooks/                   # Auth, biometric, filters, theme
│   ├── server/                  # TRPC server + shared utilities
│   ├── shared/                  # Shared TS types + constants
│   ├── drizzle/                 # Drizzle ORM schema + migrations
│   ├── tests/                   # Jest test suite
│   ├── package.json
│   └── tsconfig.json
│
└── docs/                        # Full multi‑page documentation suite
🚀 Quickstart
Backend (Flask)
bash
poetry install
poetry run alembic upgrade head
poetry run flask run
Mobile App (Expo)
bash
cd mobile-app
pnpm install
pnpm start
TRPC Server
Runs automatically with the mobile app.

🔥 Key Platform Capabilities
Compliance & Lending
AI‑driven agreement scanning

Auto‑lock borrower accounts

Ethical lending enforcement

Fraud Detection
Transaction validation

Pattern analysis

Auto‑lock on suspicious activity

Smart Contracts
Simulated execution

Event‑driven workflows

Open Banking
Plaid account linking

Transaction ingestion

PDF statement parsing

Telemetry
Redis TTL traces

Rate‑limit counters

Health checks

Audit logs

🧪 Testing
Backend
bash
poetry run pytest --cov=app
Mobile App
bash
cd mobile-app
pnpm test
🛡️ Security Requirements
JWT rotation required

SECRET_KEY rotation required

Admin seed password must be changed in production

OAuth secrets handled server‑side

No secrets stored in mobile bundle

🧭 Developer Onboarding
Full onboarding guide located at:

Code
docs/05-developer-onboarding.md
🛠️ CI/CD Pipeline
Full pipeline documentation:

Code
docs/06-ci-cd-pipeline.md
📊 Database ERD
Full ERD located at:

Code
docs/04-database-erd.md
📡 API Reference
REST + TRPC + Drizzle schema:

Code
docs/09-api-reference.md
📜 OpenAPI Specification
REST endpoints only:

Code
docs/10-openapi.yaml
🧭 Operator Handbook
Daily, weekly, monthly operational tasks:

Code
docs/07-operator-handbook.md
📝 Release Notes
Versioned release history:

Code
docs/08-release-notes.md
🧱 Monorepo Architecture Diagram
Full monorepo diagram:

Code
docs/11-monorepo-architecture-diagram.md
🎉 This repository is now a complete, unified fintech platform.
Backend → TRPC → Mobile App → Database → Telemetry
All in one cockpit‑grade, maintainable, operator‑friendly monorepo.
