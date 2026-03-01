# Copilot instructions for PlaidBridgeOpenBankingApi

## Repo layout
- `PlaidBridgeOpenBankingApi/` — Flask backend (Python 3.12)
- `mobile-app/` — React Native / Expo app with tRPC server

## Build / Test
- Setup: `python -m pip install -r requirements.txt`
- Run tests: `python -m pytest -q`
- Lint: `ruff check .`
- Fix formatting: `black .` then `ruff check --fix .`

## Commands to run before committing
- `ruff check .`
- `black .`
- `python -m pytest -q`

## Code Style / Conventions
- Target Python >= 3.10. Use PEP 604 union types when appropriate.
- Use type hints for public functions.
- Prefer small, well-tested functions (single responsibility).
- Use structured logging via the standard logging module.
- Keep line length <= 100 characters.

## Backend conventions (Flask)
- Use the app factory (`create_app`) and keep extensions as singletons in `app/extensions.py`.
- Prefer blueprint auto-discovery with explicit ordering for critical blueprints.
- Models in `app/models`, services in `app/services`, tests in `app/tests`.
- MySQL in production, SQLite in tests.
- Alembic migrations must follow SQLAlchemy naming conventions (MetaData naming).
- Use `python -m alembic -c alembic.ini ...` when `alembic` is not on PATH.

## Auth & security
- Dual auth: Flask-Login (session/web) and Flask-JWT-Extended (API).
- JWT revocation uses blocklist pattern (`RevokedToken` model).
- Rate limiting uses Redis when available, with in-memory fallback.

## Mobile app conventions
- React Native + Expo Router; server uses tRPC with `publicProcedure`, `protectedProcedure`, `adminProcedure`.
- Serialization with `superjson`.
- Drizzle ORM for the server.
- Use pnpm scripts for running, testing, and migrations.

## Commit messages
- Use Conventional Commits (e.g., `fix:`, `feat:`, `chore:`).
- Prefix breaking changes with `BREAKING CHANGE:` in the body.

## Workflow / Branches
- Create feature branches from `main`.
- Run `ruff check . && python -m pytest -q` before opening PR.
- Include a short description and testing notes in PRs.

## Security & Secrets
- Never commit secrets or API keys.
- If Copilot suggests secrets, remove and rotate them.
- Use `.env` for local-only variables and add to `.gitignore`.

## When to use Plan mode
- For multi-file refactors, use `/plan` and approve the plan before code generation.
