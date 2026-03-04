Copilot.md — Operational Behavior for AI Agents in This Monorepo
1. Purpose
This file defines how Copilot should behave when generating, modifying, or reasoning about code inside the PlaidBridgeOpenBankingApi monorepo.
It complements:

AGENTS.md (architecture + context)

.github/instructions/*.instructions.md (modular rules)

Copilot must follow this file when producing code, tests, migrations, documentation, or refactors.

2. General Behavior Expectations
2.1. Copilot must operate as a senior engineer
Prefer clarity over cleverness.

Prefer explicitness over magic.

Prefer maintainability over shortcuts.

Prefer narratable, operator‑visible behavior.

Prefer defensive coding patterns.

2.2. Copilot must respect the monorepo boundaries
Backend code lives under PlaidBridgeOpenBankingApi/app/.

Mobile code lives under mobile-app/.

Docs live under docs/.

CI/CD lives under .github/workflows/.

Copilot must not mix concerns across these boundaries.

2.3. Copilot must follow the repo’s architectural patterns
Flask application factory

Centralized extension initialization

Blueprint‑based routing

Service‑layer business logic

SQLAlchemy ORM

Alembic migrations

Redis‑backed rate limiting

Telemetry + tracing

DTO‑driven request/response patterns

Strict typing (Python 3.10+)

3. Backend Code Generation Rules
3.1. Application Factory
Copilot must always integrate new features through:

Code
app/__init__.py
app/extensions.py
app/blueprints/
app/services/
app/models/
Never bypass create_app() or init_extensions().

3.2. Blueprints
When adding endpoints:

Create or extend a file under app/blueprints/

Register via the blueprint registry

Keep handlers thin

Move logic into app/services/

3.3. Services
All business logic must live in app/services/.

Rules:

No DB access in routes

No long logic in routes

No circular imports

Use dependency injection where possible

3.4. Models
When modifying models:

Update SQLAlchemy models under app/models/

Generate migrations using Alembic

Never manually edit migration history

Maintain naming conventions

3.5. Rate Limiting
Copilot must preserve the fallback logic:

Redis available → real limiter

Redis unavailable → _NoopLimiter

Testing → always _NoopLimiter

3.6. Telemetry
Copilot must not remove or bypass:

tracing

probes

audit logs

operator‑visible telemetry

4. Mobile App Code Generation Rules
4.1. API Client
Copilot must generate mobile API calls using:

Code
mobile-app/lib/
mobile-app/constants/config.ts
4.2. Authentication
Copilot must:

store JWT in SecureStore

attach JWT to all requests

handle 401 → logout flow

4.3. Drizzle
Copilot must:

keep schema changes in drizzle/

avoid breaking migrations

maintain type‑safety

4.4. Expo Router
Copilot must:

place screens under mobile-app/app/

avoid mixing UI and business logic

keep hooks in mobile-app/hooks/

5. Documentation Behavior
5.1. Docs must match code
When Copilot generates or modifies backend or mobile code, it must update:

docs/03-backend-architecture.md

docs/12-mobile-architecture.md

docs/09-api-reference.md

docs/10-openapi.yaml

5.2. MkDocs
Copilot must maintain:

consistent navigation

consistent formatting

consistent cross‑links

6. Testing Behavior
6.1. Backend Tests
Copilot must:

use pytest

place tests under app/tests/

use fixtures for app + DB

test Redis up/down behavior

test fraud/compliance/lending logic

test PDF parsing

test Plaid flows

6.2. Mobile Tests
Copilot must:

use Jest

place tests under mobile-app/tests/

mock API calls

test auth flows

test navigation

7. CI/CD Behavior
7.1. Copilot must ensure CI passes
CI requires:

ruff check .

black --check .

pytest -q

migrations valid

docs build

type checks

7.2. Redis Matrix
Copilot must ensure tests work:

with Redis

without Redis

7.3. Coverage
Copilot must maintain or improve coverage.

8. Security Behavior
8.1. Secrets
Copilot must never:

hardcode secrets

commit credentials

log sensitive data

8.2. JWT
Copilot must:

use flask‑jwt‑extended

validate tokens

check blocklist

8.3. PII
Copilot must:

use pii_manager.py when handling sensitive data

avoid logging PII

9. Operator Expectations
9.1. Code must be narratable
Every change must be:

explainable

reversible

observable

operator‑visible

9.2. Code must be cockpit‑grade
Copilot must:

maintain telemetry

maintain probes

maintain audit logs

maintain admin UI behavior

9.3. Code must be safe
Copilot must:

preserve fraud/compliance logic

preserve lending rules

preserve dispute workflows

preserve PDF parsing accuracy

10. Copilot Interaction Rules
10.1. Use /plan for multi‑file changes
Copilot must produce a plan before:

refactors

migrations

multi‑module changes

cross‑repo changes

10.2. Use /delegate for tangential tasks
Copilot must isolate:

documentation updates

test generation

cleanup tasks

10.3. Never hallucinate architecture
Copilot must rely on:

AGENTS.md

Copilot.md

.github/instructions/

actual repo structure

10.4. Never invent endpoints
Copilot must use:

docs/09-api-reference.md

docs/10-openapi.yaml

app/routes/

app/blueprints/

11. Common Commands
Backend
Code
ruff check .
black .
pytest -q
flask db migrate -m "msg"
flask db upgrade
Mobile
Code
npm test
expo start
12. Remediation & Monitoring
Copilot must help operators:

test Redis fallback

verify blueprint deduping

remove runtime artifacts

update .gitignore

validate environment variables

rotate secrets

run smoke tests

inspect telemetry

End of Copilot.md
