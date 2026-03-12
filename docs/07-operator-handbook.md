# 🧭 Operator Handbook — Financial Powerhouse Platform

This handbook defines daily, weekly, and monthly operational responsibilities for platform operators and provides concise runbooks for common checks and incident response.

---

## Overview
Operators are responsible for system availability, telemetry, security posture, and integrations (Plaid, Treasury Prime). Follow the checks below and escalate according to the incident response procedure.

Technical Identity: `PlaidBridgeOpenBankingApi`  
Platform Identity: Financial Powerhouse Platform

---

## 🟢 Daily Tasks
- Check `/health`
  - Verify HTTP 200 and basic service metrics.
- Review fraud and compliance logs for high-severity alerts.
- Monitor Redis telemetry and rate-limit counters.
- Verify Plaid and Treasury Prime connectivity (sanity checks).
- Review application error logs and backlog for spikes.
- Confirm that scheduled jobs (if any) completed successfully.

---

## 🟡 Weekly Tasks
- Rotate JWT and `SECRET_KEY` if required by policy (or verify rotation schedule).
- Review recent migrations for correctness and any pending rollbacks.
- Run smoke tests against staging.
- Validate admin seed presence and credentials (do not store secrets in plaintext).
- Review recurring alerts for noise and adjust thresholds.

---

## 🔵 Monthly Tasks
- Full secrets rotation (rotate API keys, DB credentials, third-party keys).
- Audit database integrity (consistency checks, FK validity, row counts for key tables).
- Review rate-limit counters and capacity planning metrics.
- Validate PDF parser accuracy against sample statements (spot-check).
- Review access logs and audit trails for suspicious activity.

---

## 🚨 Incident Response (Runbook)
1. Triage
   - Pull recent logs and alerts.
   - Identify impacted services, scope (number of users/borrowers), and severity.
2. Containment
   - For fraud-related incidents: lock affected borrower accounts (auto-lock or manual).
   - If secrets are suspected compromised: rotate secrets immediately and revoke tokens.
3. Mitigation
   - Run the full smoke test suite against staging and (if safe) production read-only endpoints.
   - Apply emergency fix if available (follow hotfix PR process).
4. Recovery
   - Restore affected services, confirm with smoke tests and monitoring.
   - Gradually re-enable locked accounts after verification if appropriate.
5. Postmortem
   - Document timeline, root cause, remedial actions, and next steps.
   - Create follow-up tickets for long-term fixes.

---

## 🧪 Smoke Test Checklist
- `/health` returns OK (200)
- DB connection is healthy
- Redis connection is healthy
- Plaid sandbox reachable (run a minimal auth/account call)
- Treasury Prime reachable (run a minimal API call)
- Admin seed present and valid
- Background jobs processed (if applicable)

Example quick check (curl):
```bash
curl -fS --max-time 5 https://api.example.com/health || echo "health check failed"
