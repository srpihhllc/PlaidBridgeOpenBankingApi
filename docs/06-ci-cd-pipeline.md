# 📘 Financial Powerhouse Platform
### (PlaidBridgeOpenBankingApi — Backend API & Unified Monorepo)

# 📘 Financial Powerhouse Platform
### (PlaidBridgeOpenBankingApi — Backend API & Unified Monorepo)

# 🛠 CI/CD Pipeline — GitHub Actions

The platform uses a multi‑workflow CI/CD pipeline to ensure reliability, maintainability, and operator clarity.

---

# 1. Backend CI

- Install Python + Poetry  
- Install dependencies  
- Run Alembic migrations  
- Run pytest  
- Enforce coverage  
- Lint  

---

# 2. Mobile CI

- Install Node + pnpm  
- Install dependencies  
- TypeScript checks  
- Jest tests  

---

# 3. Monorepo Integrity

- Validate repo structure  
- Validate docs presence  
- Validate OpenAPI spec  
- Validate TS types  

---

# 4. Staging Deploy Simulation

- Build backend  
- Build mobile  
- Validate environment  
- Dry‑run deployment  

---

# 5. Docs Deploy

- Build docs  
- Publish to GitHub Pages  

---

# 🔐 Branch Protection

- Required checks: backend, mobile, integrity  
- Required reviews  
- No direct pushes to `main`

---

**Technical Identity:** `PlaidBridgeOpenBankingApi`
**Platform Identity:** Financial Powerhouse Platform
