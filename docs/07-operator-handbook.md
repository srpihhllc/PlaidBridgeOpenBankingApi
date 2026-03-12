# Operator Handbook — Financial Powerhouse Platform (PDF Edition)

This handbook defines the operational responsibilities for the Financial Powerhouse Platform across daily, weekly, and monthly cadences.

Technical Identity: `PlaidBridgeOpenBankingApi`  
Platform Identity: Financial Powerhouse Platform

---

## 1. Purpose
Define operator responsibilities and runbooks for daily, weekly, and monthly maintenance and incident response.

---

## 2. System Overview
- Flask backend API (compliance, fraud, contracts, telemetry)  
- React Native / Expo mobile app  
- TRPC server (shared TypeScript)  
- PostgreSQL + Drizzle ORM  
- Redis telemetry and rate limiting  
- GitHub Actions CI/CD

---

## 3. Daily Checklist
1. Verify the `/health` endpoint returns HTTP 200.
2. Inspect Redis telemetry for:
   - Rate‑limit anomalies
   - TTL trace outliers
3. Review fraud auto‑locks and compliance flags.
4. Confirm CI pipeline is green on the `main` branch.
5. Scan recent error logs for spikes or new stack traces.

---

## 4. Weekly Checklist
1. Rotate JWT and `SECRET_KEY` if required by policy (or verify rotation schedule).
2. Review audit logs for:
   - Manual overrides
   - Failed or pending migrations
   - Suspicious access patterns
3. Run the full test suites:
   - Backend: `poetry run pytest --cov=app`
   - Mobile: `cd mobile-app && pnpm test`
4. Validate that scheduled jobs completed successfully.

---

## 5. Monthly Checklist
1. Review ERD and check for schema drift versus migrations.
2. Validate onboarding and operator docs are current.
3. Review release notes and plan the next version cadence.
4. Audit third‑party dependencies for security advisories and apply patches as appropriate.

---

## 6. Incident Response (High Level)

### Triage
- Identify impacted services (API, mobile, TRPC, DB, Redis).
- Determine scope (users affected, data impact, uptime SLA).

### Contain
- Lock affected borrower accounts (auto-lock or manual).
- Disable or throttle risky flows if needed.

### Recover
- Restore from backups if data corruption occurred.
- Apply hotfixes following the hotfix PR process and verify in staging before production rollout.

### Post‑mortem
- Document timeline and root cause.
- Add tests, telemetry, and runbook improvements to prevent recurrence.
- Create follow-up tickets with owners and SLAs for fixes.

---

## 7. Contact & Escalation
- Engineering on‑call rotation: (populate)
- Compliance contact: (populate)
- Security contact: (populate)

Store contact lists securely (not in plaintext in the repository).

---

## Appendix — Quick Commands

Validate backend tests and coverage:
```bash
poetry install
poetry run pytest --cov=app
