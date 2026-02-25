# 🧭 Operator Handbook — Financial Powerhouse Platform

This handbook defines daily, weekly, and monthly operational responsibilities for platform operators.

---

# 🟢 Daily Tasks

- Check `/health`  
- Review fraud/compliance logs  
- Monitor Redis telemetry  
- Verify Plaid/Treasury Prime connectivity  
- Review error logs  

---

# 🟡 Weekly Tasks

- Rotate JWT + SECRET_KEY (if required)  
- Review migrations  
- Run smoke tests  
- Validate admin seed  

---

# 🔵 Monthly Tasks

- Full secrets rotation  
- Audit DB integrity  
- Review rate‑limit counters  
- Validate PDF parser accuracy  

---

# 🚨 Incident Response

- Lock borrower accounts on fraud flags  
- Rotate secrets immediately if compromised  
- Run full smoke test suite  
- Review audit logs  

---

# 🧪 Smoke Test Checklist

- `/health` returns OK  
- DB connected  
- Redis connected  
- Plaid sandbox reachable  
- Treasury Prime reachable  
- Admin seed present  

---

# 📦 Deployment Expectations

- Migrations applied  
- Secrets updated  
- Logs clean  
- Telemetry stable
