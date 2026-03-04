# Security Rules

## Authentication
- Use JWT via `flask_jwt_extended`.
- Never expose sensitive claims in tokens.
- Validate all user input.

## Secrets
- Never commit secrets or credentials.
- Use environment variables for configuration.

## Rate Limiting
- Use `flask-limiter` with Redis when available.
- Fallback to `_NoopLimiter` in testing.

## Logging
- Avoid logging sensitive data (tokens, passwords, PII).
