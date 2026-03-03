## Recommended additions (Integrations, Admin, CI/CD, Security, Observability)

### Plaid & OAuth provider integration patterns
- OAuth callback URLs:
  - Use environment-specific _external_ urls (e.g. REDIRECT_URI staging/prod) and register both sandbox and production callbacks with providers.
  - Keep callback handlers minimal: validate state, persist tokens, emit telemetry, then redirect to UX.
- Token lifecycle:
  - Persist long-lived tokens (refresh/access) securely (encrypted fields in DB or secrets manager).
  - Implement refresh-on-demand + background refresh job for token expiry.
  - Use idempotent stored-request keys for webhook/event processing.
- Webhooks:
  - Verify provider signatures and timestamp recency.
  - Use idempotency keys (DB/redis) so webhook retries are safe.
  - Enqueue webhook work to background workers (not inline).
- Sandbox vs prod:
  - Toggle via config (PLAID_ENV=dev|sandbox|prod). Tests should use fixtures that stub provider responses.
  - Provide recorded fixtures for common provider flows (oauth success/failure, callback, webhook).

### OAuth providers (Google/Microsoft, etc.)
- Centralize provider config in app/extensions or app/config_providers.py.
- Use consistent state parameter handling and CSRF protection for provider redirects.
- Persist provider user info mapping (provider_id) to internal user.
- Provide a dev-mode override to bypass SSO for local testing (guarded by TESTING).

### Cockpit / Admin UI routing & templates
- Blueprint conventions:
  - Admin UI blueprint uses url_prefix `/admin` and endpoint prefix `admin.`; API admin uses `admin_api*`.
  - Tile endpoints use `admin.tile_*` naming and should live under `/admin/tile/...`.
- Permissions:
  - All admin routes require `@admin_required` or roles via `roles_required(...)`.
  - Template links linking to admin endpoints should be guarded by `{% if 'admin.some_route' in view_functions %}` when optional.
- Tiles & dashboards:
  - Keep tiles stateless and callable as small endpoints returning partials.
  - Use server-side feature flags for experimental tiles.
- Template audit:
  - Run `python -m app.scripts.audit` during dev and CI to detect missing `url_for` endpoints.

### CI/CD & Release workflow
- Workflows:
  - Use matrix jobs for Python versions + optional DB variants.
  - Cache pip/venv and poetry/pip-tools artifacts for speed.
- Coverage:
  - CI computes coverage and fails PR if below threshold. Locally reproduce with:
    - coverage run --source=PlaidBridgeOpenBankingApi -m pytest
    - coverage report -m
- Secrets:
  - Keep provider secrets (Plaid client id/secret, OAuth client secrets) in GitHub Actions secrets or a vault, never in repo.
- Branch protection:
  - Require passing checks + 1-2 reviewers before merge.
- Dependabot:
  - Enable Dependabot for Python and GitHub Actions; triage high/critical security PRs ASAP.

### Security & secrets handling
- Don't store plaintext secrets in DB or repo. Use KMS / Hashi Vault / GitHub Secrets for runtime.
- Rotate provider secrets and tokens periodically; document rotation steps in repo runbook.
- Enforce minimum session/cookie settings: Secure, HttpOnly, SameSite, short JWT expiry + refresh rotation.

### Observability & telemetry
- Telemetry:
  - Emit traces for auth, payments, Plaid flows, and important background jobs.
  - Keep sampling for high-throughput endpoints and full traces for error flows.
- Error reporting:
  - Sentry or similar for exceptions (with scrubbing PII).
  - Structured logs (JSON) and a retention policy.

### Migrations & data seeds
- Use alembic for migrations. Workflow:
  - developer: make migration -> run locally -> open PR with migration files
  - CI: run alembic check (no pending migrations) and run migrations in an ephemeral DB for integration tests
- Seeds: provide small seed scripts for local dev (seed_admin, seed_mock_data). Large data loads should be optional.

### Developer tips & troubleshooting
- Template audit: python -m app.scripts.audit
- Reproduce failing tests without coverage gating:
  - pytest -q -p no:pytest_cov -p no:cov
- Reproduce CI coverage locally:
  - coverage run --source=PlaidBridgeOpenBankingApi -m pytest
  - coverage report -m
- Local Redis/DB:
  - Use docker-compose.dev for running DB + Redis locally.
- Rollbacks:
  - Merge rollbacks via git revert <merge_commit> and rollback DB migration with `alembic downgrade -1` if needed.

### Ops / Release checklist (short)
- Run tests & template audit
- Ensure CI coverage + lint pass
- Verify DB migration plan & cleanup
- Deploy to staging; run smoke tests (admin login/trace export/dispute review)
- Monitor logs/telemetry for 30–60 minutes
- Promote to prod if green
