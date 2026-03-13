# 🔐 GitHub Secrets Setup Guide
**Enterprise Deployment - Secrets Configuration**

---

## Overview

This guide walks you through configuring all required GitHub repository secrets for enterprise deployment. These secrets are injected into GitHub Actions workflows and deployment targets.

---

## Prerequisites

```bash
# Install GitHub CLI
# Windows: winget install GitHub.cli
# Mac: brew install gh
# Linux: See https://github.com/cli/cli#installation

# Authenticate
gh auth login

# Verify you can access your repository
gh repo view
```

---

## Secret Categories

### 1. Core Application Secrets (REQUIRED)
### 2. Database Secrets (REQUIRED)
### 3. External API Secrets (REQUIRED)
### 4. PythonAnywhere Secrets (if deploying to PythonAnywhere)
### 5. Azure Secrets (if deploying to Azure)
### 6. Optional Third-Party Secrets

---

## 🔑 1. Core Application Secrets

### SECRET_KEY
**Purpose:** Flask session encryption, CSRF protection  
**Security Level:** Critical - NEVER expose

**Generate:**
```bash
# Generate secure random key
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

**Set:**
```bash
# Copy the output from above command
gh secret set SECRET_KEY --body "YOUR_GENERATED_KEY_HERE"
```

**Verification:**
```bash
gh secret list | grep SECRET_KEY
# Expected: SECRET_KEY (Set...)
```

---

### JWT_SECRET_KEY
**Purpose:** JWT token signing and verification  
**Security Level:** Critical - NEVER expose

**Generate:**
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

**Set:**
```bash
gh secret set JWT_SECRET_KEY --body "YOUR_GENERATED_KEY_HERE"
```

---

## 💾 2. Database Secrets

### DB_USER
**Purpose:** Database username  
**Security Level:** High

**Set:**
```bash
gh secret set DB_USER --body "plaidbridge_prod_user"
```

---

### DB_PASSWORD
**Purpose:** Database password  
**Security Level:** Critical

**Generate Strong Password:**
```bash
python -c "import secrets, string; chars = string.ascii_letters + string.digits + '!@#$%^&*'; print(''.join(secrets.choice(chars) for _ in range(32)))"
```

**Set:**
```bash
gh secret set DB_PASSWORD --body "YOUR_GENERATED_PASSWORD"
```

---

### DB_HOST
**Purpose:** Database server hostname/IP  
**Security Level:** Medium

**Examples:**
- **Azure:** `plaidbridge.mysql.database.azure.com`
- **AWS RDS:** `plaidbridge.abc123.us-east-1.rds.amazonaws.com`
- **GCP:** `35.xxx.xxx.xxx`
- **PythonAnywhere:** `username.mysql.pythonanywhere-services.com`

**Set:**
```bash
gh secret set DB_HOST --body "your-database-host.com"
```

---

### DB_NAME
**Purpose:** Database name  
**Security Level:** Low

**Set:**
```bash
gh secret set DB_NAME --body "plaidbridge_production"
```

---

## 🏦 3. External API Secrets

### PLAID_CLIENT_ID
**Purpose:** Plaid API authentication  
**Security Level:** High  
**Where to find:** https://dashboard.plaid.com/team/keys

**Set:**
```bash
# Get from Plaid Dashboard → Team Settings → Keys → Production
gh secret set PLAID_CLIENT_ID --body "your_production_client_id"
```

---

### PLAID_SECRET
**Purpose:** Plaid API secret key  
**Security Level:** Critical  
**Where to find:** https://dashboard.plaid.com/team/keys

**Set:**
```bash
# IMPORTANT: Use PRODUCTION secret, not sandbox!
gh secret set PLAID_SECRET --body "your_production_secret"
```

---

### REDIS_URL
**Purpose:** Redis cache connection  
**Security Level:** High

**Format:** `redis://[username]:[password]@[host]:[port]/[db]`

**Examples:**
- **Local:** `redis://localhost:6379/0`
- **Azure Cache:** `rediss://:PASSWORD@plaidbridge.redis.cache.windows.net:6380/0`
- **AWS ElastiCache:** `redis://plaidbridge.abc123.cache.amazonaws.com:6379/0`
- **Redis Cloud:** `redis://default:PASSWORD@redis-12345.c1.us-east-1-2.ec2.cloud.redislabs.com:12345`

**Set:**
```bash
gh secret set REDIS_URL --body "redis://your-redis-url:6379/0"
```

---

### MAIL_PASSWORD
**Purpose:** SMTP authentication for sending emails  
**Security Level:** High

**Gmail App Password:**
```bash
# 1. Enable 2FA on your Google account
# 2. Go to: https://myaccount.google.com/apppasswords
# 3. Create app password for "Mail"
# 4. Use the 16-character password generated
```

**SendGrid:**
```bash
# 1. Sign up at https://sendgrid.com
# 2. Create API Key under Settings → API Keys
# 3. Use the API key as password
```

**Set:**
```bash
gh secret set MAIL_PASSWORD --body "your_app_specific_password"
```

---

## 🐍 4. PythonAnywhere Secrets (Optional)

Only required if deploying to PythonAnywhere.

### PYTHONANYWHERE_USERNAME
**Purpose:** SSH authentication  
**Security Level:** Medium

**Set:**
```bash
gh secret set PYTHONANYWHERE_USERNAME --body "srpihhllc"
```

---

### PYTHONANYWHERE_PASSWORD
**Purpose:** SSH authentication  
**Security Level:** Critical

**Set:**
```bash
gh secret set PYTHONANYWHERE_PASSWORD --body "your_pythonanywhere_password"
```

---

## ☁️ 5. Azure Secrets (Optional)

Only required if deploying to Azure Container Apps.

### ACR_LOGIN_SERVER
**Purpose:** Azure Container Registry URL  
**Format:** `yourregistry.azurecr.io`

**Find:**
```bash
az acr list --query "[].{Name:name, LoginServer:loginServer}" -o table
```

**Set:**
```bash
gh secret set ACR_LOGIN_SERVER --body "yourregistry.azurecr.io"
```

---

### ACR_USERNAME
**Purpose:** ACR authentication  
**Same as:** Registry name

**Set:**
```bash
gh secret set ACR_USERNAME --body "yourregistry"
```

---

### ACR_PASSWORD
**Purpose:** ACR authentication  
**Find:**
```bash
az acr credential show --name yourregistry --query "passwords[0].value" -o tsv
```

**Set:**
```bash
gh secret set ACR_PASSWORD --body "$(az acr credential show --name yourregistry --query 'passwords[0].value' -o tsv)"
```

---

### AZURE_RESOURCE_GROUP
**Purpose:** Resource group for Container App  
**Format:** `plaidbridge-production-rg`

**Set:**
```bash
gh secret set AZURE_RESOURCE_GROUP --body "plaidbridge-production-rg"
```

---

### AZURE_CONTAINERAPP_NAME
**Purpose:** Container App name  
**Format:** `plaidbridge-api`

**Set:**
```bash
gh secret set AZURE_CONTAINERAPP_NAME --body "plaidbridge-api"
```

---

### AZURE_CREDENTIALS
**Purpose:** Azure Service Principal for authentication  
**Format:** JSON object

**Create Service Principal:**
```bash
# Create service principal
az ad sp create-for-rbac \
  --name "plaidbridge-github-actions" \
  --role contributor \
  --scopes /subscriptions/YOUR_SUBSCRIPTION_ID/resourceGroups/plaidbridge-production-rg \
  --sdk-auth

# Output will be JSON - copy the entire output
```

**Set:**
```bash
# Paste the JSON output from above command
gh secret set AZURE_CREDENTIALS --body '{
  "clientId": "...",
  "clientSecret": "...",
  "subscriptionId": "...",
  "tenantId": "...",
  "activeDirectoryEndpointUrl": "...",
  "resourceManagerEndpointUrl": "...",
  "activeDirectoryGraphResourceId": "...",
  "sqlManagementEndpointUrl": "...",
  "galleryEndpointUrl": "...",
  "managementEndpointUrl": "..."
}'
```

---

## 🔧 6. Optional Third-Party Secrets

### OPENAI_API_KEY (for AI features)
```bash
gh secret set OPENAI_API_KEY --body "sk-..."
```

### TWILIO_ACCOUNT_SID (for SMS)
```bash
gh secret set TWILIO_ACCOUNT_SID --body "AC..."
```

### TWILIO_AUTH_TOKEN
```bash
gh secret set TWILIO_AUTH_TOKEN --body "your_twilio_auth_token"
```

### STRIPE_SECRET_KEY (for payments)
```bash
gh secret set STRIPE_SECRET_KEY --body "sk_live_..."
```

---

## ✅ Verification Checklist

### Step 1: List All Secrets
```bash
gh secret list
```

### Step 2: Verify Required Secrets

**Minimum required for deployment:**
```
☐ SECRET_KEY
☐ JWT_SECRET_KEY
☐ DB_USER
☐ DB_PASSWORD
☐ DB_HOST
☐ DB_NAME
☐ PLAID_CLIENT_ID
☐ PLAID_SECRET
☐ REDIS_URL
☐ MAIL_PASSWORD
```

**Platform-specific (choose one):**

**For PythonAnywhere:**
```
☐ PYTHONANYWHERE_USERNAME
☐ PYTHONANYWHERE_PASSWORD
```

**For Azure:**
```
☐ ACR_LOGIN_SERVER
☐ ACR_USERNAME
☐ ACR_PASSWORD
☐ AZURE_RESOURCE_GROUP
☐ AZURE_CONTAINERAPP_NAME
☐ AZURE_CREDENTIALS
```

### Step 3: Test Deployment
```bash
# Trigger test deployment
gh workflow run staging-deploy.yml

# Monitor workflow
gh run watch
```

---

## 🔄 Secret Rotation Schedule

### Immediate Rotation (if compromised)
- SECRET_KEY
- JWT_SECRET_KEY
- DB_PASSWORD
- PLAID_SECRET

### Quarterly Rotation
- MAIL_PASSWORD
- ACR_PASSWORD
- AZURE_CREDENTIALS

### Annual Rotation
- All other secrets

**Rotation Command:**
```bash
# Example: Rotate SECRET_KEY
NEW_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
gh secret set SECRET_KEY --body "$NEW_KEY"

# Redeploy to apply new secret
gh workflow run production-deploy.yml
```

---

## 🆘 Common Issues

### Issue: "Secret not found"
**Solution:**
```bash
# Check secret name (case-sensitive)
gh secret list

# Recreate secret
gh secret set SECRET_NAME --body "value"
```

### Issue: "Authentication failed in workflow"
**Solution:**
```bash
# Verify secret value (doesn't show actual value, just status)
gh secret list

# Delete and recreate
gh secret delete SECRET_NAME
gh secret set SECRET_NAME --body "new_value"
```

### Issue: "Azure authentication failed"
**Solution:**
```bash
# Regenerate Azure credentials
az ad sp create-for-rbac --name "plaidbridge-github-actions" --role contributor --sdk-auth

# Update secret
gh secret set AZURE_CREDENTIALS --body '...'
```

---

## 📝 Batch Setup Script

Save time with this batch setup script:

```bash
#!/bin/bash
# setup-github-secrets.sh

echo "🔐 Setting up GitHub Secrets for PlaidBridge Enterprise Deployment"
echo "=================================================================="

# Core secrets
echo "Generating SECRET_KEY..."
SECRET_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
gh secret set SECRET_KEY --body "$SECRET_KEY"

echo "Generating JWT_SECRET_KEY..."
JWT_SECRET_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
gh secret set JWT_SECRET_KEY --body "$JWT_SECRET_KEY"

# Database (prompt for values)
read -p "Enter DB_USER: " DB_USER
gh secret set DB_USER --body "$DB_USER"

read -sp "Enter DB_PASSWORD: " DB_PASSWORD
echo
gh secret set DB_PASSWORD --body "$DB_PASSWORD"

read -p "Enter DB_HOST: " DB_HOST
gh secret set DB_HOST --body "$DB_HOST"

read -p "Enter DB_NAME [plaidbridge_production]: " DB_NAME
DB_NAME=${DB_NAME:-plaidbridge_production}
gh secret set DB_NAME --body "$DB_NAME"

# Plaid
read -p "Enter PLAID_CLIENT_ID: " PLAID_CLIENT_ID
gh secret set PLAID_CLIENT_ID --body "$PLAID_CLIENT_ID"

read -sp "Enter PLAID_SECRET: " PLAID_SECRET
echo
gh secret set PLAID_SECRET --body "$PLAID_SECRET"

# Redis
read -p "Enter REDIS_URL: " REDIS_URL
gh secret set REDIS_URL --body "$REDIS_URL"

# Mail
read -sp "Enter MAIL_PASSWORD: " MAIL_PASSWORD
echo
gh secret set MAIL_PASSWORD --body "$MAIL_PASSWORD"

echo ""
echo "✅ Core secrets configured!"
echo "📋 View all secrets: gh secret list"
```

**Usage:**
```bash
chmod +x setup-github-secrets.sh
./setup-github-secrets.sh
```

---

## 📚 Additional Resources

- **GitHub Secrets Documentation:** https://docs.github.com/en/actions/security-guides/encrypted-secrets
- **Azure Key Vault:** https://docs.microsoft.com/azure/key-vault/
- **Plaid Production Keys:** https://plaid.com/docs/api/env/
- **Security Best Practices:** See `CREDENTIAL_ROTATION_GUIDE.md`

---

**Last Updated:** March 7, 2026  
**Maintained by:** PlaidBridge Security Team
