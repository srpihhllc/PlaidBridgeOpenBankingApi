# 📚 Operator Documentation

Welcome to the **Financial Powerhouse API** operator docs.  
This space is designed for **future maintainers, operators, and auditors** — everything here is narratable, auditable, and cockpit‑visible.

---

## 🚀 Onboarding

- **Prerequisites**
  - Python 3.10+ installed
  - Access to Plaid sandbox credentials
  - Redis instance (TLS‑enabled recommended)
  - PostgreSQL database

- **First‑time setup**
  ```bash
  git clone https://github.com/srpihhllc/PlaidBridgeOpenBankingApi.git
  cd PlaidBridgeOpenBankingApi
  make update   # compile lockfiles
  make sync     # sync venv to lockfiles
  make test     # run full test suite
