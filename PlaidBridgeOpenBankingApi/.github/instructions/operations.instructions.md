# Operational Rules

## Required Commands
- `ruff check .`
- `black .`
- `pytest -q`

## Deployment
- Use `run.py` or WSGI entrypoint.
- Ensure Redis availability for rate limiting.
- Validate environment variables before startup.

## Developer Workflow
- Use `/plan` for multi-file changes.
- Use `/delegate` for tangential tasks.
- Maintain cockpit-grade clarity in commits and PRs.
