# 📡 API Reference — Financial Powerhouse Platform

This document provides a human‑readable reference for the REST endpoints exposed by the backend API. For machine‑readable schema (request/response models, types), see `10-openapi.yaml`.

---

## Authentication & Health

### GET /health
Liveness and readiness check. Returns 200 when the service, DB, and Redis are reachable.

### POST /auth/login
Authenticate and return JWTs (access + refresh). (See OpenAPI for payloads.)

---

## 🧩 Compliance Endpoints

### POST /review_agreement
Scan a loan agreement for problematic or unethical terms.  
- Request: agreement text or URL to stored document.  
- Response: scan results and ai_flags.

### GET /compliance_report?borrower_id=<id>
Generate a compliance report for the borrower, including flagged agreements and history.

---

## 🛡 Fraud Endpoints

### POST /validate_transaction
Analyze a transaction for fraud/anomaly signals.  
- Request: transaction details.  
- Response: risk score and recommended action (allow, review, block).

---

## 🔗 Account Linking (Plaid)

### POST /link_borrower_account
Exchange Plaid public_token for an access token and persist linked account for a borrower.

### POST /unlink_borrower_account
Unlink a borrower account. Prevent unlink when obligations remain (business logic enforcement).

### GET /generate_link_token?borrower_id=<id>
Generate a Plaid Link token for the mobile/web client.

Notes: All Plaid-related endpoints require server-side secrets and should never expose secrets to the client.

---

## 📄 Statement Processing

### POST /upload_statement
Upload a PDF statement (multipart/form-data) → extract transactions (via pdfplumber).  
- Response: parsed transactions and any parsing errors/warnings.

Notes: Large PDFs and long-running parsing should be processed asynchronously (upload → job ID → polling/webhook).

---

## ⚖ Smart Contracts

### POST /execute_contract/<id>
Simulate deterministic smart contract execution for the given contract id.  
- Request: execution parameters.  
- Response: execution outcome, events, and state projection.

---

## 📊 Financial Health

### GET /financial_health/<borrower_id>
Return the borrower's financial health score and contributing factors (transaction patterns, risk_score, linked accounts).

---

## 💱 Currency & Utilities

### POST /convert_currency
Convert amounts between currencies (placeholder FX logic). Use this for display-only conversions; integrate with a pricing/FX provider for production accuracy.

---

## 🔐 Future / Reserved Endpoints

### POST /biometric_auth
Reserved for future biometric integration (not implemented).

---

## Implementation Notes & Links
- Definitive request/response shapes and auth mechanisms are in `10-openapi.yaml`. Use that file to generate client SDKs.
- All endpoints require authentication unless explicitly listed as public (e.g., health).
- Rate limiting is enforced via Redis; check `X-RateLimit-*` headers on responses.
- Long-running jobs (PDF parsing, contract simulation) should return a job ID and use async processing. See services/docs for background worker patterns.

---

For more details and example payloads, consult:
- OpenAPI Spec — `10-openapi.yaml`
- Backend Architecture — `03-backend-architecture.md`
- Developer Onboarding — `05-developer-onboarding.md`
