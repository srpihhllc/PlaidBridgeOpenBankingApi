# 📱 Mobile Architecture — React Native / Expo

The mobile app is a full banking client built with Expo Router, TRPC, and Drizzle ORM. It provides a secure, responsive, and operator‑friendly borrower experience.

---

## Architecture Overview
- React Native UI (Expo)
- Expo Router navigation
- TRPC client → Shared TypeScript server
- Drizzle ORM schema (local / edge)
- Secure token storage (SecureStore / Keychain)
- Biometric authentication (optional + configurable)
- Themed UI (dark / light)
- Haptic feedback for supported devices

---

## Directory Structure

mobile-app/
├── app/               # Screens + navigation (Expo Router)
├── components/        # Reusable UI components
├── hooks/             # Auth, biometric, filters
├── server/            # TRPC server + utilities (for local dev)
├── shared/            # Shared TypeScript types between mobile & backend
├── drizzle/           # Schema + migrations (Drizzle)
├── tests/             # Jest + React Native Testing Library
└── package.json

---

## Security
- Do not store secrets in the bundle. Use environment variables and secrets manager.
- OAuth and Plaid/Treasury integrations are handled server‑side.
- Store tokens in SecureStore / Keychain and use appropriate TTLs.
- Biometric unlock is optional — require a fallback PIN if enabled.
- Evaluate release builds for embedded secrets before publishing.

---

## TRPC Integration
- Shared routers and types allow zero‑duplication between mobile and backend.
- TRPC client uses the shared TypeScript types for strong typing end-to-end.
- Validate inputs server-side even when client-side validation exists.

Best practice: keep shared types in `shared/` and generate/update them as part of a monorepo task so mobile and backend remain in sync.

---

## Testing
Run tests locally:

```bash
pnpm test
