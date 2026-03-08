# 🔐 Credential Rotation Guide

**CRITICAL SECURITY ACTION REQUIRED**

Due to the `.env` file being previously tracked in git history, all credentials must be rotated immediately. This guide provides step-by-step instructions for secure credential rotation.

---

## ⚠️ Why This Is Critical

Git commit history is **permanent and public** (if repository was public or shared). Even though `.env` is now untracked, anyone with access to the repository history can retrieve:
- Database credentials
- API keys (Plaid, payment processors, etc.)
- Application secrets (Flask SECRET_KEY, JWT_SECRET_KEY)
- Email/SMTP credentials
- Redis connection strings
- Any other sensitive configuration

**Assume all credentials in the old `.env` file are compromised.**

---

## 📋 Rotation Checklist

### Phase 1: Inventory (15 minutes)

1. **Locate all `.env` files:**
   ```bash
   cd PlaidBridgeOpenBankingApi
   ls -la *.env*
   ```

2. **List all credentials to rotate:**
   ```bash
   # Review current .env (DO NOT commit this output)
   cat .env | grep -E "KEY|SECRET|PASSWORD|TOKEN|CLIENT_ID|API"
   ```

3. **Document all environments:**
   - [ ] Local development
   - [ ] Testing/staging
   - [ ] Production
   - [ ] CI/CD pipelines (GitHub Actions secrets)

---

### Phase 2: Generate New Credentials (30 minutes)

#### A. Flask Application Secrets

**SECRET_KEY** (Flask session encryption):
```bash
# Generate cryptographically secure random secret
python -c "import secrets; print(secrets.token_hex(32))"
```

**JWT_SECRET_KEY** (JWT token signing):
```bash
# Use different secret from SECRET_KEY
python -c "import secrets; print(secrets.token_hex(32))"
```

**Update in `.env`:**
```env
SECRET_KEY=<new_64_char_hex_from_above>
JWT_SECRET_KEY=<different_64_char_hex_from_above>
```

---

#### B. Database Credentials

**Option 1: New Database User (Recommended)**
```sql
-- Connect to MySQL as root/admin
mysql -u root -p

-- Create new database user with strong password
CREATE USER 'plaidbridge_prod_new'@'%' IDENTIFIED BY '<STRONG_PASSWORD>';

-- Grant privileges (adjust as needed)
GRANT SELECT, INSERT, UPDATE, DELETE, CREATE, INDEX, ALTER 
ON plaidbridge_db.* TO 'plaidbridge_prod_new'@'%';

-- Flush privileges
FLUSH PRIVILEGES;

-- Verify
SHOW GRANTS FOR 'plaidbridge_prod_new'@'%';
```

**Generate strong password:**
```bash
# 32-character alphanumeric + special chars
python -c "import secrets, string; chars = string.ascii_letters + string.digits + '!@#$%^&*'; print(''.join(secrets.choice(chars) for _ in range(32)))"
```

**Update in `.env`:**
```env
DB_USER=plaidbridge_prod_new
DB_PASSWORD=<strong_password_from_above>
DB_HOST=<your_db_host>  # Keep same unless changing servers
DB_PORT=3306
DB_NAME=plaidbridge_db  # Keep same unless migrating database
```

**Option 2: Change Password for Existing User**
```sql
ALTER USER 'existing_user'@'%' IDENTIFIED BY '<NEW_STRONG_PASSWORD>';
FLUSH PRIVILEGES;
```

---

#### C. Plaid API Credentials

**Action Required:** Rotate via Plaid Dashboard

1. **Login to Plaid Dashboard:**
   - Go to https://dashboard.plaid.com
   - Navigate to Team Settings > Keys

2. **Rotate API Keys:**
   - Click "Rotate" for your environment (Sandbox/Development/Production)
   - **CRITICAL:** Copy new `client_id` and `secret` immediately
   - Old credentials will stop working after rotation

3. **Update `.env`:**
   ```env
   PLAID_CLIENT_ID=<new_client_id_from_dashboard>
   PLAID_SECRET=<new_secret_from_dashboard>
   PLAID_ENV=<sandbox|development|production>
   ```

4. **Update Webhook URL** (if applicable):
   - Verify webhook signature validation uses new secret

---

#### D. Redis Credentials (if using external Redis)

**If using Redis Cloud/ElastiCache:**
1. **Generate new password** in Redis provider dashboard
2. **Update connection string:**
   ```env
   REDIS_URL=redis://:new_password@your-redis-host:6379/0
   ```

**If self-hosted:**
```bash
# Generate strong Redis password
python -c "import secrets; print(secrets.token_urlsafe(32))"

# Update redis.conf
requirepass <new_password_from_above>

# Restart Redis
sudo systemctl restart redis
```

**Update `.env`:**
```env
REDIS_PASSWORD=<new_password>
```

---

#### E. Email/SMTP Credentials

**Gmail/SMTP Provider:**
1. Generate new **App Password** (not your account password)
2. Enable 2FA if not already enabled
3. Update `.env`:
   ```env
   MAIL_USERNAME=<your_email>
   MAIL_PASSWORD=<new_app_password>
   MAIL_SERVER=smtp.gmail.com
   MAIL_PORT=587
   MAIL_USE_TLS=True
   ```

---

#### F. Third-Party API Keys

**For each external service (Stripe, Twilio, AWS, etc.):**

1. **Locate current keys:**
   ```bash
   grep -E "API_KEY|ACCESS_KEY|AUTH_TOKEN" .env
   ```

2. **Rotate in provider dashboard:**
   - Stripe: Dashboard > Developers > API Keys > Rotate
   - Twilio: Console > Account > API Keys > Create New Key
   - AWS: IAM > Users > Security Credentials > Create Access Key

3. **Update `.env` with new keys**

---

### Phase 3: Update All Environments (1 hour)

#### A. Update `.env` Files

**Local development:**
```bash
cd PlaidBridgeOpenBankingApi
nano .env  # or vim, vscode, etc.

# Update all rotated credentials
# Save and exit

# Verify format (no syntax errors)
python -c "from dotenv import load_dotenv; import os; load_dotenv('.env'); print('✅ .env loaded successfully')"
```

**CRITICAL:** Ensure `.env` is in `.gitignore`:
```bash
# Verify .env is NOT tracked
git status .env
# Should show: "nothing to commit, working tree clean" or not listed

# If tracked, remove from git:
git rm --cached .env
git commit -m "security: ensure .env is not tracked"
```

---

#### B. Update Production Environment

**Option 1: PythonAnywhere / cPanel (Web UI)**
1. Login to hosting dashboard
2. Navigate to "Environment Variables" or "Config Vars"
3. Update each credential one by one
4. Restart web app / reload WSGI

**Option 2: SSH Access**
```bash
ssh user@production-server
cd /path/to/app
nano .env
# Update all credentials
# Save and exit

# Reload application
sudo systemctl restart plaidbridge
# or
touch /var/www/plaidbridge/tmp/restart.txt  # PythonAnywhere
```

**Option 3: Docker/Kubernetes**
```bash
# Update secrets in orchestrator
kubectl create secret generic plaidbridge-secrets \
  --from-env-file=.env.production \
  --dry-run=client -o yaml | kubectl apply -f -

# Restart pods
kubectl rollout restart deployment/plaidbridge
```

---

#### C. Update CI/CD Secrets

**GitHub Actions:**
1. Go to Repository Settings > Secrets and Variables > Actions
2. Update each secret:
   - `SECRET_KEY`
   - `JWT_SECRET_KEY`
   - `DB_PASSWORD`
   - `PLAID_CLIENT_ID`
   - `PLAID_SECRET`
   - (any others used in workflows)

**GitLab CI:**
```bash
# Via GitLab UI: Settings > CI/CD > Variables
# Or via CLI:
gitlab-ci variable create SECRET_KEY <new_value>
gitlab-ci variable create JWT_SECRET_KEY <new_value>
```

---

### Phase 4: Verification (30 minutes)

#### A. Test Database Connection

```bash
cd PlaidBridgeOpenBankingApi

# Test new DB credentials
python -c "
from app import create_app
app = create_app('production')
with app.app_context():
    from app.extensions import db
    db.engine.connect()
    print('✅ Database connection successful')
"
```

#### B. Test Application Startup

```bash
# Run in development mode first
FLASK_ENV=development python run.py

# Should see:
# ✅ No authentication errors
# ✅ No database connection errors
# ✅ Application running on http://127.0.0.1:5000
```

#### C. Test External API Connections

**Plaid:**
```bash
python -c "
import os
from dotenv import load_dotenv
load_dotenv()
import plaid
from plaid.api import plaid_api

configuration = plaid.Configuration(
    host=plaid.Environment.Sandbox,
    api_key={
        'clientId': os.getenv('PLAID_CLIENT_ID'),
        'secret': os.getenv('PLAID_SECRET'),
    }
)
client = plaid_api.PlaidApi(plaid.ApiClient(configuration))
print('✅ Plaid credentials valid')
"
```

**Redis:**
```bash
python -c "
from app.utils.redis_utils import get_redis_client
client = get_redis_client()
client.set('test_key', 'test_value')
assert client.get('test_key') == b'test_value'
print('✅ Redis connection successful')
"
```

#### D. Run Test Suite

```bash
# Ensure tests pass with new config
cd PlaidBridgeOpenBankingApi
python -m pytest -x --tb=short

# Expected: All tests pass
# If failures, check TestingConfig uses correct test credentials
```

---

### Phase 5: Revoke Old Credentials (CRITICAL)

**⚠️ DO THIS AFTER verifying new credentials work**

#### A. Revoke Old Database User

```sql
-- Connect as DB admin
mysql -u root -p

-- Drop old compromised user
DROP USER 'old_username'@'%';
FLUSH PRIVILEGES;

-- Verify
SELECT User, Host FROM mysql.user WHERE User='old_username';
-- Should return empty result
```

#### B. Delete Old Plaid Keys

1. Login to Plaid Dashboard
2. Team Settings > Keys
3. Click "Delete" on old API keys
4. Confirm deletion

#### C. Revoke Old API Keys

**For each third-party service:**
- Delete old API keys from provider dashboard
- Verify old keys return 401 Unauthorized when tested

---

### Phase 6: Document & Monitor (15 minutes)

#### A. Update Internal Documentation

Create `SECRETS_ROTATED.md` (DO NOT COMMIT):
```markdown
# Credential Rotation Log

**Date:** 2026-03-07
**Performed by:** [Your Name]
**Reason:** Security incident - .env exposed in git history

## Credentials Rotated:
- [x] SECRET_KEY
- [x] JWT_SECRET_KEY
- [x] DB_USER / DB_PASSWORD
- [x] PLAID_CLIENT_ID / PLAID_SECRET
- [x] REDIS_PASSWORD
- [x] MAIL_PASSWORD
- [x] [Other services...]

## Environments Updated:
- [x] Local development
- [x] Staging
- [x] Production
- [x] CI/CD (GitHub Actions)

## Old Credentials Revoked:
- [x] Database user dropped
- [x] Plaid old keys deleted
- [x] [Other revocations...]

## Verification Tests Passed:
- [x] Database connection
- [x] Application startup
- [x] Plaid API calls
- [x] Redis connection
- [x] Full test suite

**Next Rotation Due:** 2026-06-07 (Quarterly)
```

#### B. Set Calendar Reminders

**Quarterly rotation schedule:**
- March 7, 2026 ✅ (Initial rotation)
- June 7, 2026 (Next rotation)
- September 7, 2026
- December 7, 2026

**Add to team calendar:**
```
Event: Quarterly Credential Rotation
Reminder: 1 week before
Attendees: DevOps team, Security lead
```

#### C. Enable Monitoring Alerts

**Database Access Monitoring:**
```sql
-- Enable MySQL general log temporarily to monitor access
SET GLOBAL general_log = 'ON';
SET GLOBAL log_output = 'TABLE';

-- Check for unauthorized access attempts
SELECT * FROM mysql.general_log 
WHERE command_type = 'Connect' 
AND user_host NOT LIKE '%authorized_host%';
```

**Application Logs:**
```bash
# Monitor for authentication errors
tail -f /var/log/plaidbridge/app.log | grep -E "401|403|Unauthorized|Invalid credentials"
```

---

## 🚨 Incident Response (If Breach Detected)

If you detect unauthorized access **after** rotation:

1. **Immediately revoke ALL credentials again**
2. **Lock down database:**
   ```sql
   -- Temporarily restrict access
   REVOKE ALL PRIVILEGES ON plaidbridge_db.* FROM 'username'@'%';
   ```

3. **Enable maintenance mode:**
   ```bash
   # In .env
   MAINTENANCE_MODE=true
   ```

4. **Notify stakeholders:**
   - Security team
   - Database admin
   - Management
   - Affected users (if PII exposed)

5. **Review access logs:**
   ```bash
   # Database access
   sudo grep "mysql" /var/log/auth.log
   
   # Application access
   sudo grep "POST /auth/login" /var/log/nginx/access.log
   ```

6. **Forensic analysis:**
   - Git repository access logs
   - Cloud provider audit logs (AWS CloudTrail, etc.)
   - Database query logs

7. **Regulatory compliance:**
   - GDPR: Notify data protection authority within 72 hours if PII compromised
   - PCI DSS: Notify payment processor if payment data affected
   - SOC2: Document incident for auditors

---

## ✅ Completion Verification

**Before marking this complete, verify:**

- [ ] All credentials in old `.env` rotated
- [ ] All production environments updated
- [ ] CI/CD secrets updated
- [ ] Database connection tested successfully
- [ ] Application startup verified in all environments
- [ ] External API connections tested (Plaid, etc.)
- [ ] Full test suite passes
- [ ] Old credentials revoked/deleted
- [ ] Team notified of credential changes
- [ ] Documentation updated
- [ ] Monitoring alerts enabled
- [ ] Quarterly rotation calendar reminder set

---

## 📞 Support Contacts

**Database Issues:**
- DB Admin: [contact info]
- Hosting Provider Support: [support URL]

**API Credential Issues:**
- Plaid Support: https://dashboard.plaid.com/support
- Stripe Support: https://support.stripe.com

**Application Issues:**
- DevOps Team: [slack channel / email]
- On-Call Engineer: [pager duty / phone]

---

**Last Updated:** March 7, 2026  
**Next Review:** June 7, 2026 (Quarterly rotation)
