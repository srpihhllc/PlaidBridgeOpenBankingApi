# Testing Rules

## Tools
- Use `pytest` as the test runner.
- Tests must run cleanly with `pytest -q`.

## Requirements
- All new features require unit tests.
- Prefer small, isolated tests.
- Avoid mocking internal logic unnecessarily.
- Use fixtures for database, Redis, and app factory setup.

## Workflow
- Run `pytest -q` before committing.
- Copilot should generate tests when adding new endpoints or utilities.
