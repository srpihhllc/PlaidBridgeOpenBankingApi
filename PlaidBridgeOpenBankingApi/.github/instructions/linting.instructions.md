# Linting Rules

## Tools
- Use `ruff` for linting and modernization.
- Use `black` for formatting.

## Requirements
- Code must pass `ruff check .` with zero errors.
- Modernize Python code to 3.10+ (PEP 604 unions, no `typing.Dict`, etc.).
- No unused imports, dead code, or wildcard imports.
- Maintain consistent formatting with `black .`.

## Workflow
- Run `ruff check . && black .` before committing.
- Fix all UP-series modernization warnings.
