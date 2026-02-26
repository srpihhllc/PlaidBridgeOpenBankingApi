AGENTS.md — PlaidBridgeOpenBankingApi
Architecture, Domain Model, Operator Rules, and AI Agent Guidance for the Full Monorepo
1. Purpose
This document provides architectural context and operator rules for AI agents and contributors working inside the PlaidBridgeOpenBankingApi monorepo. It describes how the backend, mobile app, documentation suite, CI/CD, and fintech domain logic fit together. Copilot should use this file as context, not instructions.

2. Monorepo Structure
Code
PlaidBridgeOpenBankingApi/
│
├── PlaidBridgeOpenBankingApi/                # Flask backend
│   ├── app/
│   │   ├── admin/                            # admin cockpit UI
│   │   ├── agents/                           # agent orchestration
│   │   ├── analytics/                        # analytics engines
│   │   ├── api/                              # API modules (disputes, fintech, validation)
│   │   ├── blueprints/                       # blueprint modules (admin, api_v1, auth, plaid, etc.)
│   │   ├── cli/ / cli_commands/              # CLI tooling
│   │   ├── cockpit/                          # cockpit dashboards
│   │   ├── constants/                        # global constants
│   │   ├── decorators/                       # decorators (auth, rate limit, etc.)
│   │   ├── docs/                             # backend docs
│   │   ├── dto/                              # request/response DTOs
│   │   ├── filters/                          # Jinja filters
│   │   ├── forms/                            # WTForms
│   │   ├── letters/                          # letter generation
│   │   ├── logging/                          # logging utilities
│   │   ├── middleware/                       # middleware layers
│   │   ├── models/                           # SQLAlchemy models (50+ domain models)
│   │   ├── probes/                           # health probes
│   │   ├── processors/                       # PDF, CSV, transaction processors
│   │   ├── registry/                         # registry patterns
│   │   ├── routes/                           # API endpoints (admin, api, cockpit, pulse, disputes, lenders, etc.)
│   │   ├── scripts/                          # operational scripts
│   │   ├── security/                         # API key auth, isolation, MFA
│   │   ├── services/                         # business logic (fraud, compliance, lending, scoring, statements)
│   │   ├── signals/                          # Flask signals
│   │   ├── telemetry/                        # telemetry + tracing
│   │   ├── templates/                        # Jinja templates
│   │   ├── tests/                            # pytest suite
│   │   ├── utils/                            # helpers
│   │   └── views/                            # view-layer routes
│   ├── migrations/                           # Alembic migrations
│   ├── .github/instructions/                 # modular Copilot rules
│   ├── AGENTS.md                             # this file
│   ├── run.py                                # local entrypoint
│   ├── wsgi.py                               # production entrypoint
│   ├── requirements.txt
│   ├── alembic.ini
│   └── ...
│
├── mobile-app/                               # React Native / Expo app
│   ├── app/                                  # Expo Router screens
│   ├── assets/images/
│   ├── components/
│   ├── constants/                            # API config, theme, env
│   ├── drizzle/                              # SQLite schema + migrations
│   ├── hooks/
│   ├── lib/                                  # API client, auth, utilities
│   ├── scripts/
│   ├── server/                               # TRPC dev server
│   ├── shared/
│   ├── tests/
│   ├── BIOMETRIC_AUTHENTICATION.md
│   ├── app.config.ts
│   ├── design.md
│   ├── drizzle.config.ts
│   ├── package.json
│   ├── tsconfig.json
│   └── ...
│
├── docs/                                     # MkDocs documentation suite
│   ├── 01-system-architecture.md
│   ├── 03-backend-architecture.md
│   ├── 04-database-erd.md
│   ├── 05-developer-onboarding.md
│   ├── 06-ci-cd-pipeline.md
│   ├── 07-operator-handbook.md
│   ├── 09-api-reference.md
│   ├── 10-openapi.yaml
│   ├── 11-monorepo-architecture-diagram.md
│   ├── 12-mobile-architecture.md
│   └── index.md
│
├── .github/workflows/                        # CI/CD
├── Makefile
├── README.md
└── ...
Copilot must treat this as a single unified platform, not separate projects.

3. Backend Architecture
The backend is a large-scale fintech API with:

Application factory (create_app())

Centralized extension initialization

SQLAlchemy ORM with 50+ domain models

Alembic migrations

JWT authentication

Redis-backed rate limiting

Telemetry + tracing

Fraud detection

Compliance scanning

PDF statement parsing

Financial health scoring

Lending cognition engine

Dispute resolution engine

Plaid integration

Treasury Prime integration (sandbox)

Cockpit dashboards

Admin UI

Subscriber UI

API key auth

MFA (TOTP)

Email + SMS services

create_app() responsibilities
Load config

Initialize extensions

Register blueprints (from app/blueprints/)

Register CLI commands

Configure logging

Apply security headers

Initialize telemetry

Initialize rate limiter

Initialize Redis

init_extensions(app) initializes:
SQLAlchemy

Migrate

JWT

Redis client

Rate limiter

Mail

SocketIO

LoginManager

CSRF

Telemetry

Copilot should never bypass init_extensions(app).

4. Rate Limiting Logic
The limiter is initialized via _init_limiter(app, redis_enabled).

Rules:

If TESTING=True → _NoopLimiter

If RATE_LIMIT_ENABLED=False → _NoopLimiter

If Redis available → real limiter

If Redis fails → fallback to _NoopLimiter

This fallback behavior must always be preserved.

5. Models
Models live in:

Code
app/models/
Includes:

Users, lenders, borrowers

Loan agreements

Ledger + credit ledger

Bank accounts, institutions, statements

Transactions + vault transactions

Fraud reports

Disputes

Complaints

MFA codes

Registry + schema events

Timeline + timeline events

Tradelines

Subscriber profiles

Audit logs

Access tokens

Plaid items

Conventions:

SQLAlchemy declarative base

Naming conventions from extensions.py

Python 3.10+ typing

No circular imports

UUID or integer PKs depending on domain

6. Routes & Blueprints
Routes live in:

Code
app/routes/
Blueprints live in:

Code
app/blueprints/
Blueprints include:

admin_routes.py

api_routes.py

api_v1_routes.py

auth_routes.py

plaid_routes.py

subscriber_routes.py

grants_routes.py

liquidity_routes.py

letter_routes.py

debug_routes.py

pulse_routes.py

cfpb_routes.py

todo_routes.py

Rules:

Use Blueprints

Keep handlers thin

Business logic belongs in services/

Validate input

Return JSON responses

7. Services Layer
Services live in:

Code
app/services/
Includes:

Fraud detection

Fraud analytics

Compliance AI

Lending cognition

Statement service

PDF parsing

PDF generation

Category analytics

Transaction analysis

Tradeline service

Lender verification

Card manager

MFA service

PII manager

Payment auditor

Symphony AI

Registry service

Balance service

Guidelines:

No DB logic in routes

Keep services testable

Use dependency injection where possible

8. Plaid Integration
Flow:

Mobile app launches Plaid Link

Receives public_token

Sends to Flask: /plaid/exchange

Flask exchanges for:

access_token

item_id

Flask stores tokens

Mobile app fetches accounts + transactions via Flask

Mobile app never talks directly to Plaid.

9. Fraud, Compliance, Lending, and Statements
The backend includes:

AI-driven compliance scanning

Fraud detection + analytics

Lending cognition engine

Dispute resolution

Complaint logging

PDF statement parsing

Bank transaction extraction

Financial health scoring

Smart contract simulation

Currency conversion

Biometric authentication placeholder

Copilot must preserve:

operator visibility

narratable decisions

auditability

10. Mobile App Architecture
The mobile app lives in:

Code
mobile-app/
Uses:

Expo Router

TypeScript

SecureStore for JWT

Fetch/Axios for API calls

Drizzle + SQLite

TRPC dev server

Mobile → Backend Communication
API base URL lives in:

Code
mobile-app/constants/config.ts
Must use LAN IP, not localhost.

Authentication Flow
Login → /auth/login

Receive JWT

Store in SecureStore

Attach to all requests

Backend validates + checks blocklist

Mobile endpoints used
/auth/login

/auth/register

/plaid/exchange

/plaid/accounts

/plaid/transactions

/upload_statement

/validate_transaction

/financial_health

/review_agreement

/generate_link_token (legacy)

11. Documentation Suite
Docs live in:

Code
docs/
Includes:

System architecture

Backend architecture

Mobile architecture

ERD

API reference

OpenAPI spec

CI/CD

Operator handbook

Release notes

MkDocs deploys via:

Code
.github/workflows/docs.yml
12. CI/CD
CI/CD includes:

Linting (ruff, black)

Testing (pytest)

Coverage enforcement

Redis up/down matrix

Migration checks

Docs deployment

Security scanning

Operator workflows

13. Developer Workflow
Use /plan for multi-file changes

Use /delegate for tangential tasks

Always run:

ruff check .

black .

pytest -q

Follow conventional commits

Maintain cockpit-grade clarity in PRs

14. Local Setup
Backend
Code
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export FLASK_APP=PlaidBridgeOpenBankingApi.app:create_app
flask run
Mobile
Code
cd mobile-app
npm install
expo start
15. Remediation & Monitoring
Test Redis fallback

Verify blueprint deduping

Remove runtime artifacts

Keep .gitignore updated

Validate environment variables

Review logs for sensitive data

Run smoke tests

Rotate secrets

End of AGENTS.md
