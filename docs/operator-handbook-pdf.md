# 📘 Financial Powerhouse Platform
### (PlaidBridgeOpenBankingApi — Backend API & Unified Monorepo)

# 📘 Financial Powerhouse Platform
### (PlaidBridgeOpenBankingApi — Backend API & Unified Monorepo)

# Operator Handbook (PDF Edition)

## 1. Purpose
This handbook defines the operational responsibilities for the Financial Powerhouse Platform across daily, weekly, and monthly cadences.

---

## 2. System Overview
- Flask backend API (compliance, fraud, contracts, telemetry)
- React Native / Expo mobile app
- TRPC server
- PostgreSQL + Drizzle ORM
- Redis telemetry
- GitHub Actions CI/CD

---

## 3. Daily Checklist
1. Verify /health endpoint returns 200.
2. Check Redis telemetry for:
   - Rate‑limit anomalies
   - TTL trace outliers
3. Review fraud auto‑locks and compliance flags.
4. Confirm CI pipeline is green on main.

---

## 4. Weekly Checklist
1. Rotate JWT and SECRET_KEY (per security policy).
2. Review audit logs for:
   - Manual overrides
   - Failed migrations
   - Suspicious access patterns
3. Run full test suite:
   poetry run pytest --cov=app
   cd mobile-app && pnpm test

---

## 5. Monthly Checklist
1. Review ERD and schema drift.
2. Validate onboarding docs are current.
3. Review release notes and plan next version.
4. Audit third‑party dependencies for security advisories.

---

## 6. Incident Response (High Level)

### Triage
- Identify impacted services (API, mobile, TRPC, DB, Redis).

### Contain
- Lock affected accounts.
- Disable risky flows if needed.

### Recover
- Restore from backups if data corruption is detected.

### Post‑mortem
- Document root cause.
- Add tests and telemetry to prevent recurrence.

---

## 7. Contact & Escalation
- Engineering on‑call rotation
- Compliance contact
- Security contact

---

**Technical Identity:** `PlaidBridgeOpenBankingApi`
**Platform Identity:** Financial Powerhouse Platform
