FRONTEND DEVELOPER GUIDE
This is a concise senior-developer playbook to align the mobile mobile-app workspace with the backend BFF and core API.

Sections
Quick checks

Environment

Auth contract

tRPC contract tests

Screen-by-screen checklist

CI & QA

Quick checks
Branch: target branch for these docs is fix/restore-dummy-test-routes (confirmed by requestor). If you want a different target, abort and specify one.

Local dev commands:

Bash
cd mobile-app
pnpm install
pnpm run dev:server # starts BFF/tRPC server
pnpm run dev:metro  # starts Expo
Environment
Frontend public envs (set for Expo builds and local dev):

EXPO_PUBLIC_API_BASE_URL

EXPO_PUBLIC_OAUTH_PORTAL_URL

EXPO_PUBLIC_OAUTH_SERVER_URL

EXPO_PUBLIC_APP_ID

EXPO_PUBLIC_OWNER_OPEN_ID

EXPO_PUBLIC_OWNER_NAME

Server envs (BFF / proxies): DATABASE_URL, JWT_SECRET, BUILT_IN_FORGE_API_URL, BUILT_IN_FORGE_API_KEY, PLAID_*

Auth contract (summary)
Web: cookie-based (backend sets cookie via /api/oauth/callback). Frontend uses credentials: 'include'.

Native: backend returns { app_session_id } from /api/oauth/mobile; frontend stores token and uses Authorization: Bearer <token>.

tRPC contract tests
Add a small contract test to run against a running dev server validating key endpoints: accounts.list, transactions.list, preferences.get.

Screen-by-screen
See mobile-app/docs/frontend-checklist.yaml for the mapping and QA checks. Implement error handling, loading states and Zod schema validation alignment for each screen.

CI & QA
A recommended CI workflow is added at .github/workflows/mobile-app-integration.yml. It installs pnpm, starts the BFF, runs checks and tests.