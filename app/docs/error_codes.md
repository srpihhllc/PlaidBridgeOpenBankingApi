# 📖 Error Code Taxonomy

This document defines the canonical error codes used across the PlaidBridge Open Banking API.  
Every API response must return a uniform envelope with one of these codes when `status="error"`.

---

## 🔑 Authentication & Authorization

| Code            | HTTP Status       | When to Use                                                                 | Example Routes                          |
|-----------------|------------------|------------------------------------------------------------------------------|-----------------------------------------|
| **E_AUTH_FAIL** | 401 Unauthorized | Authentication sequence failed (invalid credentials, expired/invalid MFA code, bad/expired JWT). | `/auth/token`, `/verify_mfa_code`, global 401 handler |
| **E_UNAUTHORIZED** | 403 Forbidden | User is authenticated but not permitted by policy (not approved, MFA not enabled, lender not verified). | `/auth/token` (unapproved user), `/request_mfa_code`, `/link_borrower_account` |

---

## 🔑 Validation & Input

| Code            | HTTP Status       | When to Use                                                                 | Example Routes          |
|-----------------|------------------|------------------------------------------------------------------------------|-------------------------|
| **E_VALIDATION** | 400 Bad Request | Request payload is malformed, missing required fields, or contains invalid values. | `/register`, `/tradelines`, `/request_mfa_code` |

---

## 🔑 Resource & Existence

| Code            | HTTP Status       | When to Use                                                                 | Example Routes          |
|-----------------|------------------|------------------------------------------------------------------------------|-------------------------|
| **E_NOT_FOUND** | 404 Not Found    | Requested resource does not exist or is not accessible to the current user.  | `/loans/<id>`, `/execute_contract/<id>` |

---

## 🔑 Implementation & Stubs

| Code                  | HTTP Status       | When to Use                                                                 | Example Routes          |
|-----------------------|------------------|------------------------------------------------------------------------------|-------------------------|
| **E_NOT_IMPLEMENTED** | 501 Not Implemented | Functionality is a stub or placeholder, not yet implemented.                 | `/validate_transaction`, `/generate_fraud_pdf_report` |

---

## 🔑 External & Infrastructure

| Code            | HTTP Status       | When to Use                                                                 | Example Routes          |
|-----------------|------------------|------------------------------------------------------------------------------|-------------------------|
| **E_EXTERNAL_API** | 503 Service Unavailable / 500 Internal Server Error | Downstream dependency (Gemini, Plaid, Redis, etc.) failed or returned invalid response. | Dispute blast, Gemini summarize/TTS |
| **E_DB_WRITE**  | 500 Internal Server Error | Database commit failed (IntegrityError, OperationalError, etc.).             | `/register`, `/tradelines`, `/loans` |
| **E_GENERIC**   | 500 Internal Server Error | Catch‑all for unexpected server errors not covered by other codes.           | Fraud report generation fallback |

---

## 🔑 Rate Limiting

| Code            | HTTP Status       | When to Use                                                                 | Example Routes          |
|-----------------|------------------|------------------------------------------------------------------------------|-------------------------|
| **E_RATE_LIMIT** | 429 Too Many Requests | Client exceeded allowed request quota.                                      | Any throttled route (future limiter integration) |

---

## 🧭 Operator Notes

- **Always log** the error with `request_id`, `path`, `ip`, and `user_id` (if available).  
- **SchemaEvents** should be emitted for significant failures (e.g. `DISPUTE_BLAST_FAILED`, `FRAUD_REPORT_GENERATED`).  
- **Metrics counters** should increment per error code for cockpit dashboards.  
- **Consistency is key**: never mix `E_AUTH_FAIL` and `E_UNAUTHORIZED`. Use the taxonomy above.

---

## 📦 Example Error Response

```json
{
  "status": "error",
  "data": {},
  "error": {
    "code": "E_AUTH_FAIL",
    "message": "Invalid credentials"
  },
  "meta": {
    "timestamp": "2025-10-08T12:34:56Z",
    "request_id": "a1b2c3d4"
  }
}
