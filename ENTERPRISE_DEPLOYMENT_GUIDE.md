# 🚀 Enterprise Deployment Guide
**PlaidBridge Open Banking API - Production Deployment**

---

## 📋 Table of Contents
1. [Deployment Architecture](#deployment-architecture)
2. [Supported Platforms](#supported-platforms)
3. [Prerequisites](#prerequisites)
4. [GitHub Secrets Configuration](#github-secrets-configuration)
5. [Deployment Workflows](#deployment-workflows)
6. [Environment Management](#environment-management)
7. [Monitoring & Rollback](#monitoring--rollback)
8. [Troubleshooting](#troubleshooting)

---

## 🏗️ Deployment Architecture

### Multi-Platform Strategy
Your application supports deployment to multiple enterprise platforms:

```
┌─────────────────────────────────────────────────────┐
│          GitHub Actions CI/CD Pipeline              │
│  (Triggered by: push to production or version tag)  │
└──────────┬──────────────────────────┬───────────────┘
           │                          │
    ┌──────▼──────┐            ┌──────▼──────────┐
    │ PythonAny   │            │  Azure Container│
    │   where     │            │      Apps       │
    │  (uWSGI)    │            │   (Docker)      │
    └──────┬──────┘            └────────┬────────┘
           │                            │
    ┌──────▼──────────────────────┬────▼────────┐
    │   Production Environment    │             │
    │  - PostgreSQL/MySQL         │  Monitoring │
    │  - Redis Cache              │  & Logging  │
    │  - Plaid API Integration    │             │
    └─────────────────────────────┴─────────────┘
```

### Deployment Targets

| Platform | Type | Best For | URL Pattern |
|----------|------|----------|-------------|
| **PythonAnywhere** | Traditional Hosting | Quick deployment, managed Python | `https://srpihhllc.pythonanywhere.com` |
| **Azure Container Apps** | Containerized | Auto-scaling, global distribution | `https://[app-name].azurecontainerapps.io` |

---

## 🎯 Supported Platforms

### 1. PythonAnywhere Deployment
**Configuration:** `uwsgi.ini`  
**Workflow:** `.github/workflows/production-deploy.yml` → `deploy-pythonanywhere` job

**Features:**
- ✅ Managed Python environment
- ✅ Automatic SSL certificates
- ✅ SSH deployment via Git pull
- ✅ uWSGI production server
- ✅ Static file serving

**Process:**
1. SSH into PythonAnywhere
2. Pull latest code from `production` branch
3. Install/upgrade dependencies
4. Run database migrations
5. Reload uWSGI by touching WSGI file

### 2. Azure Container Apps
**Configuration:** `Dockerfile`  
**Workflow:** `.github/workflows/production-deploy.yml` → `deploy-azure` job

**Features:**
- ✅ Docker containerization
- ✅ Auto-scaling (0-N instances)
- ✅ Blue/Green deployments
- ✅ Integrated monitoring
- ✅ Secret management via Key Vault

**Process:**
1. Build Docker image with versioning
2. Push to Azure Container Registry (ACR)
3. Update Container App configuration
4. Deploy new container version
5. Health check verification

---

## ✅ Prerequisites

### Required Tools
```bash
# GitHub CLI (for workflow management)
gh --version  # Install: https://cli.github.com/

# Azure CLI (for Azure deployments)
az --version  # Install: https://docs.microsoft.com/cli/azure/install-azure-cli

# Docker (for local testing)
docker --version

# Git
git --version
```

### Account Requirements
- [ ] GitHub repository with Actions enabled
- [ ] PythonAnywhere account (if using PythonAnywhere)
- [ ] Azure subscription with Container Apps enabled (if using Azure)
- [ ] Plaid developer account (production credentials)
- [ ] Database hosting (PostgreSQL/MySQL)
- [ ] Redis hosting (optional but recommended)

---

## 🔐 GitHub Secrets Configuration

### Step 1: Navigate to Repository Settings
```bash
# Via GitHub CLI
gh secret list

# Or via web:
# https://github.com/[YOUR_USERNAME]/[REPO_NAME]/settings/secrets/actions
```

### Step 2: Configure Required Secrets

#### Core Application Secrets
```bash
# Flask security
gh secret set SECRET_KEY --body "$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
gh secret set JWT_SECRET_KEY --body "$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"

# Database
gh secret set DB_USER --body "your_production_db_username"
gh secret set DB_PASSWORD --body "your_production_db_password"
gh secret set DB_HOST --body "your_production_db_host"
gh secret set DB_NAME --body "plaidbridge_production"

# Plaid (production credentials from dashboard.plaid.com)
gh secret set PLAID_CLIENT_ID --body "your_plaid_production_client_id"
gh secret set PLAID_SECRET --body "your_plaid_production_secret"

# Redis
gh secret set REDIS_URL --body "redis://your_redis_host:6379/0"

# Email/SMTP
gh secret set MAIL_PASSWORD --body "your_smtp_password"
```

#### PythonAnywhere Secrets (if using)
```bash
gh secret set PYTHONANYWHERE_USERNAME --body "srpihhllc"
gh secret set PYTHONANYWHERE_PASSWORD --body "your_pythonanywhere_password"
```

#### Azure Secrets (if using)
```bash
# Azure Container Registry
gh secret set ACR_LOGIN_SERVER --body "yourregistry.azurecr.io"
gh secret set ACR_USERNAME --body "yourregistry"
gh secret set ACR_PASSWORD --body "your_acr_password"

# Azure Container Apps
gh secret set AZURE_RESOURCE_GROUP --body "plaidbridge-production-rg"
gh secret set AZURE_CONTAINERAPP_NAME --body "plaidbridge-api"

# Azure Service Principal (JSON format)
gh secret set AZURE_CREDENTIALS --body '{
  "clientId": "your-client-id",
  "clientSecret": "your-client-secret",
  "subscriptionId": "your-subscription-id",
  "tenantId": "your-tenant-id"
}'
```

### Secret Verification
```bash
# List all configured secrets
gh secret list

# Expected output:
# SECRET_KEY
# JWT_SECRET_KEY
# DB_USER
# DB_PASSWORD
# DB_HOST
# DB_NAME
# PLAID_CLIENT_ID
# PLAID_SECRET
# REDIS_URL
# MAIL_PASSWORD
# ... (platform-specific secrets)
```

---

## 🚦 Deployment Workflows

### Workflow 1: Production Deployment (Recommended)
**File:** `.github/workflows/production-deploy.yml`  
**Triggers:**
- Push to `production` branch
- Version tags (`v*.*.*`)
- Manual dispatch

**Jobs:**
1. **Validate** - Pre-flight checks, version extraction
2. **Backend Build** - Tests, migrations, coverage
3. **Mobile Build** - TypeScript checks, linting, tests
4. **Deploy to PythonAnywhere** - SSH deployment
5. **Deploy to Azure** - Container build & deploy
6. **Verify Deployment** - Smoke tests, health checks

**Usage:**
```bash
# Option 1: Push to production branch
git checkout production
git merge main
git push origin production

# Option 2: Create version tag
git tag -a v1.0.0 -m "Production release 1.0.0"
git push origin v1.0.0

# Option 3: Manual trigger
gh workflow run production-deploy.yml
```

### Workflow 2: Staging Deployment
**File:** `.github/workflows/staging-deploy.yml`  
**Triggers:**
- Push to `staging` branch
- Manual dispatch

**Usage:**
```bash
# Deploy to staging
git checkout staging
git merge develop
git push origin staging
```

### Workflow 3: CI/CD (Continuous Integration)
**Files:** `.github/workflows/backend-ci.yml`, `.github/workflows/mobile-ci.yml`  
**Triggers:**
- Push to `main` branch
- Pull requests to `main`

**Purpose:** Validate code quality before merging

---

## 🌍 Environment Management

### Branch Strategy
```
main/master    → Development & CI
  └─ staging   → Pre-production testing
      └─ production → Live production
```

### Environment Variables by Platform

#### PythonAnywhere (.env file on server)
```bash
# SSH into PythonAnywhere
ssh srpihhllc@ssh.pythonanywhere.com

# Create .env file
cd ~/PlaidBridgeOpenBankingApi/PlaidBridgeOpenBankingApi
nano .env

# Paste production environment variables
# (See PlaidBridgeOpenBankingApi/.env.example)
```

#### Azure Container Apps (Managed Secrets)
```bash
# Set secrets via Azure CLI
az containerapp secret set \
  --name plaidbridge-api \
  --resource-group plaidbridge-production-rg \
  --secrets \
    secret-key=$SECRET_KEY \
    jwt-secret-key=$JWT_SECRET_KEY \
    db-user=$DB_USER \
    db-password=$DB_PASSWORD \
    plaid-secret=$PLAID_SECRET \
    redis-url=$REDIS_URL

# Secrets are automatically injected as environment variables
```

---

## 📊 Monitoring & Rollback

### Health Checks
Both deployment targets include health check endpoints:
```bash
# PythonAnywhere
curl https://srpihhllc.pythonanywhere.com/health

# Azure
curl https://plaidbridge-api.azurecontainerapps.io/health
```

### Monitoring Endpoints
- `/health` - Basic health check
- `/api/v1/metrics` - Application metrics (if configured)
- Azure Application Insights (Azure deployments)

### Rollback Procedures

#### PythonAnywhere Rollback
```bash
# SSH into server
ssh srpihhllc@ssh.pythonanywhere.com

# Rollback to previous commit
cd ~/PlaidBridgeOpenBankingApi
git log --oneline -10  # Find previous version
git checkout <previous-commit-hash>
source ~/.virtualenvs/myenv/bin/activate
pip install -r requirements.txt
touch /var/www/srpihhllc_pythonanywhere_com_wsgi.py
```

#### Azure Rollback
```bash
# List revisions
az containerapp revision list \
  --name plaidbridge-api \
  --resource-group plaidbridge-production-rg

# Activate previous revision
az containerapp revision activate \
  --name plaidbridge-api \
  --resource-group plaidbridge-production-rg \
  --revision <previous-revision-name>
```

---

## 🔧 Troubleshooting

### Common Issues

#### 1. Deployment Fails: Missing Secrets
```bash
# Check configured secrets
gh secret list

# Add missing secrets
gh secret set MISSING_SECRET --body "value"
```

#### 2. Database Migration Errors
```bash
# SSH into server (PythonAnywhere)
cd ~/PlaidBridgeOpenBankingApi
source ~/.virtualenvs/myenv/bin/activate
alembic downgrade -1  # Rollback one migration
alembic upgrade head  # Re-apply

# Or for Azure, check container logs
az containerapp logs show \
  --name plaidbridge-api \
  --resource-group plaidbridge-production-rg
```

#### 3. Container Build Fails
```bash
# Test Docker build locally
docker build -t test-build -f Dockerfile .

# Check .dockerignore is properly configured
cat .dockerignore
```

#### 4. Health Check Fails
```bash
# Check if /health endpoint exists
curl -v https://your-app-url.com/health

# Verify application logs
# PythonAnywhere: Check error.log in Web tab
# Azure: Use az containerapp logs show
```

### Support Resources
- **Plaid Issues:** https://dashboard.plaid.com/support
- **PythonAnywhere:** https://www.pythonanywhere.com/forums/
- **Azure:** https://docs.microsoft.com/azure/container-apps/

---

## 🎯 Quick Deployment Checklist

### Pre-Deployment
- [ ] All tests passing locally (`python test_deployment.py`)
- [ ] Database migrations created and tested
- [ ] GitHub secrets configured
- [ ] Version tag created (if applicable)
- [ ] Environment variables verified

### Deployment
- [ ] Code pushed to `production` branch
- [ ] GitHub Actions workflow triggered
- [ ] All jobs completed successfully
- [ ] Health checks passing

### Post-Deployment
- [ ] Verify application is accessible
- [ ] Check error logs for issues
- [ ] Test critical user flows
- [ ] Monitor for 24-48 hours

---

## 📝 Next Steps

1. **Configure GitHub Secrets** - Use the commands above
2. **Test Locally** - Run `python test_deployment.py`
3. **Deploy to Staging** - Test the full workflow
4. **Deploy to Production** - Push to production branch or create version tag
5. **Monitor** - Watch logs and health checks

---

**Last Updated:** March 7, 2026  
**Maintained by:** PlaidBridge Development Team
