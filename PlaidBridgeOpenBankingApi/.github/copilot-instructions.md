# PlaidBridgeOpenBankingApi — Copilot instructions (repository)

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
