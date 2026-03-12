# 🛠 CI/CD Pipeline — GitHub Actions

The platform uses a multi‑workflow CI/CD pipeline (GitHub Actions) to ensure reliability, maintainability, and operator clarity. Each workflow is narrow in scope and fast to iterate on; combined they enforce tests, linting, type safety, migration validity, and docs publishing.

---

## 1. Backend CI (workflow: backend.yml)

Responsibilities:
- Install Python (3.11+) and Poetry
- Install dependencies
- Run Alembic migrations (dry-run / validate)
- Run pytest and enforce coverage thresholds
- Run linters (flake8/ruff, mypy if used)
- Build artifact (optional) for staging deploy simulation

Best practices:
- Use a cache for Poetry/virtualenv and for pip wheels to speed runs.
- Run migrations against a throwaway/staging DB or use alembic --sql validation step for CI safety.
- Fail fast on test or lint failures.

Suggested required check name: `backend`

---

## 2. Mobile CI (workflow: mobile.yml)

Responsibilities:
- Install Node (18+) and pnpm
- Install dependencies (pnpm install)
- TypeScript checks (tsc)
- Run Jest/unit tests
- Run E2E tests when applicable (separate workflow)
- Build mobile app artifacts for staging validation

Best practices:
- Separate type-check and unit-test jobs to run in parallel.
- Cache pnpm store and node_modules.

Suggested required check name: `mobile`

---

## 3. Monorepo Integrity (workflow: integrity.yml)

Responsibilities:
- Validate repo structure (expected packages and directories)
- Validate docs presence and mkdocs build
- Validate OpenAPI spec (yaml lint + schema checks)
- Validate TypeScript types for shared packages
- Lint commit messages or enforce changelog presence if required

Best practices:
- Keep this workflow fast (only run file checks + linters) so it can gate merges without heavy compute.
- Use path filters so integrity checks run on relevant changes only.

Suggested required check name: `integrity`

---

## 4. Staging Deploy Simulation (workflow: staging-sim.yml)

Responsibilities:
- Build backend and mobile artifacts
- Validate environment variables and secrets presence (dry-run)
- Dry‑run deployment (no production changes) — smoke test scripts executed against a staging environment
- Run lightweight integration tests / smoke tests

Best practices:
- Use secrets scoped to the staging environment.
- Run canary or gradual deployment in real staging if supported by infra.

Suggested check name: `staging-simulation` (not strictly required for branch protection, but valuable before release)

---

## 5. Docs Deploy (workflow: docs.yml)

Responsibilities:
- Build docs site with mkdocs
- Run docs linters (markdownlint) and linkcheck
- Publish to GitHub Pages (or other docs host)

Best practices:
- Only deploy docs from the default branch or from merged PRs.
- Run mkdocs build to ensure site compiles.

Suggested check name: `docs`

---

## 🔐 Branch Protection & Release Controls

Recommended branch protection settings for `main` (or release branches):
- Required status checks: `backend`, `mobile`, `integrity` (and optionally `docs` / `staging-simulation`)
- Require pull request reviews before merging (1–2 reviewers depending on team)
- Require up-to-date branches before merging (rebase/merge policy)
- Enforce signed commits if desired
- Restrict who can push directly to `main` (no direct pushes)

Release process (example):
1. Merge PRs to `develop` (or open feature branches).
2. Create a release branch (`release/x.y`) from `develop` when ready.
3. Run full staging simulation and smoke tests against staging.
4. Tag and create release; run deploy workflows to production.

---

## Notes & Operational Guidance
- Name workflows and checks consistently so branch protection rules are stable.
- Keep CI jobs small and focused; move heavy integration tests to scheduled nightly runs or separate gated workflows.
- Use caching and parallel jobs to keep feedback fast.
- Audit workflow secrets, and scope tokens and deploy keys to the minimal required permissions.
- Add runbooks for CI failures and rollback procedures for releases.

---

Technical Identity: `PlaidBridgeOpenBankingApi`  
Platform Identity: Financial Powerhouse Platform
