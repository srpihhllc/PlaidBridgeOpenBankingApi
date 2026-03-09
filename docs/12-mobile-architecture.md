# 📘 Financial Powerhouse Platform
### (PlaidBridgeOpenBankingApi — Backend API & Unified Monorepo)

# 📘 Financial Powerhouse Platform
### (PlaidBridgeOpenBankingApi — Backend API & Unified Monorepo)

# 📱 Mobile Architecture — React Native / Expo

The mobile app is a full banking client built with Expo Router, TRPC, and Drizzle ORM.  
It provides a secure, responsive, and operator‑friendly borrower experience.

---

# 🏗 Architecture Overview

- React Native UI  
- Expo Router navigation  
- TRPC client → Shared TypeScript server  
- Drizzle ORM schema (local/edge)  
- Secure token storage  
- Biometric authentication  
- Themed UI (dark/light)  
- Haptic feedback  

---

# 📂 Directory Structure

mobile-app/
├── app/               # Screens + navigation
├── components/        # UI components
├── hooks/             # Auth, biometric, filters
├── server/            # TRPC server + utilities
├── shared/            # Shared TS types
├── drizzle/           # Schema + migrations
├── tests/             # Jest suite
└── package.json

Code

---

# 🔐 Security

- No secrets stored in bundle  
- OAuth handled server‑side  
- SecureStore for tokens  
- Biometric unlock  

---

# 🔌 TRPC Integration

- Shared routers  
- Shared types  
- Shared validation  
- Automatic inference  
- Zero duplication between mobile and backend  

---

# 🧪 Testing

pnpm test

Code

Covers:

- Components  
- Hooks  
- Navigation flows  
- Beneficiary management  
- Transaction filters  

---

# 📦 Build & Deployment

- Expo EAS (optional)  
- OTA updates supported  
- Environment variables loaded via `scripts/load-env.js`

---

**Technical Identity:** `PlaidBridgeOpenBankingApi`
**Platform Identity:** Financial Powerhouse Platform
