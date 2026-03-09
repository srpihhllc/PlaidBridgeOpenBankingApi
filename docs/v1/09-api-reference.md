# 📡 API Reference — Financial Powerhouse Platform

This document provides a human‑readable reference for all REST endpoints in the backend API.

For machine‑readable schema, see `10-openapi.yaml`.

---

# 🧩 Compliance Endpoints

### `POST /review_agreement`
Scan a loan agreement for unethical terms.

### `GET /compliance_report`
Generate a compliance report for a borrower.

---

# 🛡 Fraud Endpoints

### `POST /validate_transaction`
Detect suspicious activity.

---

# 🔗 Account Linking

### `POST /link_borrower_account`
Link a borrower’s bank account via Plaid.

### `POST /unlink_borrower_account`
Prevent unlinking if obligations remain.

### `GET /generate_link_token`
Generate a Plaid Link token.

---

# 📄 Statement Processing

### `POST /upload_statement`
Upload a PDF → extract transactions.

---

# ⚖ Smart Contracts

### `POST /execute_contract/<id>`
Simulate contract execution.

---

# 📊 Financial Health

### `GET /financial_health/<id>`
Return borrower financial health score.

---

# 💱 Currency

### `POST /convert_currency`
Convert between currencies (placeholder FX logic).

---

# 🔐 Authentication

### `POST /biometric_auth`
Reserved for future biometric integration.

---

# 🩺 Health

### `GET /health`
Liveness + readiness check.

---

# 📚 Related Documentation

- OpenAPI Spec — `10-openapi.yaml`
- Backend Architecture — `03-backend-architecture.md`
