# Architecture Rules

## Application Structure
- Follow the hardened Flask application factory pattern.
- Keep extensions isolated in `app/extensions.py`.
- Avoid module-level side effects.
- Use dependency injection where possible.

## Conventions
- Use Python 3.10+ typing (PEP 604 unions).
- Maintain cockpit-grade logging and error handling.
- Preserve repo-wide narratability for future maintainers.

## Endpoints
- Place routes in `app/routes/` or feature-specific modules.
- Use blueprints for modularity.
- Validate input using WTForms or custom validators.

## Database
- Use SQLAlchemy models in `app/models/`.
- Maintain naming conventions via `MetaData(naming_convention=...)`.
