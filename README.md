# Financial Powerhouse Platform
(PlaidBridgeOpenBankingApi — Unified Fintech Monorepo)

Welcome to the official documentation suite for the Financial Powerhouse Platform.
This directory contains all architecture, onboarding, operational, and API documentation for the entire monorepo.

Use this index to navigate the full system.

---

# 🏗 Architecture

- **01 — System Architecture**
  High‑level overview of the entire platform.
  → `01-system-architecture.md`

- **03 — Backend Architecture**
  Flask backend internals, services, routing, and integrations.
  → `03-backend-architecture.md`

- **11 — Monorepo Architecture Diagram**
  Visual representation of the unified monorepo.
  → `11-monorepo-architecture-diagram.md`

- **12 — Mobile Architecture**
  React Native / Expo mobile banking app architecture.
  → `12-mobile-architecture.md`

---

# 🗄 Database

- **04 — Database ERD**
  Entity‑relationship diagram and relational modeling notes.
  → `04-database-erd.md`

---

# 🧭 Developer Experience

- **05 — Developer Onboarding**
  Full setup instructions for backend, mobile, TRPC, and migrations.
  → `05-developer-onboarding.md`

---

# 🛠 CI/CD & Operations

- **06 — CI/CD Pipeline**
  GitHub Actions workflows, build steps, and deployment flow.
  → `06-ci-cd-pipeline.md`

- **07 — Operator Handbook**
  Daily, weekly, and monthly operational tasks.
  → `07-operator-handbook.md`

---

# 📝 Release Management

- **08 — Release Notes**
  Version history and major changes.
  → `08-release-notes.md`

---

# 📡 API Documentation

- **09 — API Reference**
  Human‑readable endpoint documentation.
  → `09-api-reference.md`

- **10 — OpenAPI Specification**
  Machine‑readable REST API schema.
  → `10-openapi.yaml`

---

# 🎉 End of Documentation Index

This suite is designed to be cockpit‑grade, operator‑friendly, and fully auditable.

---

✅ 2. GitHub Pages Deployment Workflow — Create this file:

File: .github/workflows/docs.yml

name: Deploy Documentation

on:
  push:
    branches:
      - main
  workflow_dispatch:

permissions:
  contents: write

jobs:
  deploy:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install MkDocs + Material
        run: |
          pip install mkdocs mkdocs-material mkdocstrings mkdocstrings-python

      - name: Deploy to GitHub Pages
        run: |
          mkdocs gh-deploy --force

What this gives you:
- Automatic docs deployment on every push to main
- Manual deploy via “Run workflow”
- MkDocs Material theme
- Fully version‑controlled documentation site

✅ 3. Combined PDF‑Ready Manual — Create this file:

File: docs/manual.md

This is a single unified manual that can be exported to PDF using MkDocs or Pandoc.

# 📘 Financial Powerhouse Platform — Complete Technical Manual

This manual consolidates all core documentation for the Financial Powerhouse Platform, including architecture, backend design, mobile architecture, ERD, CI/CD, operator workflows, and API reference.

1. System Architecture
(From 01-system-architecture.md)

2. Backend Architecture
(From 03-backend-architecture.md)

3. Database ERD
(From 04-database-erd.md)

4. Developer Onboarding
(From 05-developer-onboarding.md)

5. CI/CD Pipeline
(From 06-ci-cd-pipeline.md)

6. Operator Handbook
(From 07-operator-handbook.md)

7. Release Notes
(From 08-release-notes.md)

8. API Reference
(From 09-api-reference.md)

9. OpenAPI Specification
(From 10-openapi.yaml)

10. Monorepo Architecture Diagram
(From 11-monorepo-architecture-diagram.md)

11. Mobile Architecture
(From 12-mobile-architecture.md)

🎉 End of Manual

### ✔ Export to PDF

Using MkDocs:

mkdocs build

Using Pandoc:

pandoc docs/manual.md -o FinancialPowerhouseManual.pdf

---

# ⭐ Documentation suite is now complete:

- ✔ Full docs index
- ✔ Full docs suite
- ✔ GitHub Pages deployment
- ✔ PDF‑ready manual
- ✔ MkDocs site config
- ✔ Backend README
- ✔ Mobile architecture
- ✔ Operator handbook
- ✔ CI/CD docs
- ✔ ERD
- ✔ API reference
- ✔ OpenAPI spec

---

# 🚀 Financial Powerhouse API

![Build Status](https://github.com/srpihhllc/PlaidBridgeOpenBankingApi/actions/workflows/ci.yml/badge.svg)
[![codecov](https://codecov.io/gh/srpihhllc/PlaidBridgeOpenBankingApi/branch/main/graph/badge.svg)](https://codecov.io/gh/srpihhllc/PlaidBridgeOpenBankingApi)
![All Clear](https://img.shields.io/badge/All%20Clear-Passing-green)

> A cockpit‑grade fintech API that enforces ethical lending, detects fraud, integrates with open banking, and provides operator‑visible telemetry for every financial flow.

---

## 📑 Table of Contents
- [📊 Project Health at a Glance](#-project-health-at-a-glance)
- [🔗 Quick Links](#-quick-links)
- [✨ Features](#-features)
  - [AI‑Driven Compliance](#ai-driven-compliance)
  - [Fraud Detection & Security](#fraud-detection--security)
  - [Borrower–Lender Integration](#borrowerlender-integration)
  - [PDF Statement Processing](#pdf-statement-processing)
  - [Smart Contract Automation (Simulated)](#smart-contract-automation-simulated)
  - [Financial Health Scoring](#financial-health-scoring)
  - [Currency Conversion](#currency-conversion)
  - [Biometric Authentication (Planned)](#biometric-authentication-planned)
  - [Health Checks & Error Handling](#health-checks--error-handling)
- [🧩 Design Philosophy](#-design-philosophy)
- [🔁 3‑Tier Sync Loop](#-3-tier-sync-loop)
- [⚙️ Setup](#️-setup)
- [🤝 Contributing](#-contributing)

---

## 📊 Project Health at a Glance

| Check                  | Status Badge                                                                 |
|-------------------------|------------------------------------------------------------------------------|
| CI Pipeline             | ![Build Status](https://github.com/srpihhllc/PlaidBridgeOpenBankingApi/actions/workflows/ci.yml/badge.svg) |
| Test Coverage           | [![codecov](https://codecov.io/gh/srpihhllc/PlaidBridgeOpenBankingApi/branch/main/graph/badge.svg)](https://codecov.io/gh/srpihhllc/PlaidBridgeOpenBankingApi) |
| Merge Safety (AllClear) | ![All Clear](https://img.shields.io/badge/All%20Clear-Passing-green)        |

---

## 🔗 Quick Links

- 🛠 **[Latest CI Runs](https://github.com/srpihhllc/PlaidBridgeOpenBankingApi/actions/workflows/ci.yml)**
- 📈 **[Coverage Dashboard (Codecov)](https://codecov.io/gh/srpihhllc/PlaidBridgeOpenBankingApi)**
- 📚 **[Operator Docs](app/docs/README.md)** (onboarding, runbooks, migrations)
- 🧪 **[Test Reports](https://github.com/srpihhllc/PlaidBridgeOpenBankingApi/actions)** (JUnit + mypy artifacts)

---

## ✨ Features

### AI‑Driven Compliance
- Scans loan agreements for unethical terms (hidden fees, predatory rates).
- Flags violations and generates compliance reports.
- Locks borrower and lender accounts after repeated issues.

### Fraud Detection & Security
- Monitors transactions for suspicious patterns.
- Automatically locks accounts on fraud detection.

### Borrower–Lender Integration
- **Both borrowers and lenders must link accounts** to prove legitimacy.
- Secure account linking with Plaid.
- Prevents unlinking if obligations remain.

### PDF Statement Processing
- Upload and parse bank statements.
- Extracts transactions for verification.

### Smart Contract Automation (Simulated)
- Executes loan agreements as if they were blockchain contracts.
- Automatically updates agreement status.

### Financial Health Scoring
- Calculates borrower/lender health scores from transaction history.

### Currency Conversion
- Multi‑currency support with placeholder FX logic.

### Biometric Authentication (Planned)
- Endpoint reserved for fingerprint/face recognition.

### Health Checks & Error Handling
- `/health` endpoint for API status.
- Custom error handlers for 404/500.

---

## 🧩 Design Philosophy
- **Security First**: JWT auth, rate limiting, account locking.
- **Transparency**: Every decision is narratable and operator‑visible.
- **Extensibility**: Hooks for Plaid, smart contracts, biometrics, FX APIs.
- **AI at the Core**: Compliance, fraud detection, and scoring are AI‑driven.

---

## 🔁 3‑Tier Sync Loop

This project uses a 3‑tier sync loop to keep mobile clients, backend state, and external bank providers consistent and resilient.

- Tier 1 — Mobile / Client: the mobile app initiates syncs (manual or scheduled), applies deltas to a local cache, and acknowledges updates.
- Tier 2 — API / Sync Orchestrator: the Sync API persists requests, enqueues jobs, coordinates worker execution, deduplicates and enforces idempotency, and pushes notifications (push/webhook) back to clients.
- Tier 3 — Data Layer & Connectors: connector workers talk to third‑party providers (Plaid, TrueLayer, Basiq, Codat), normalize responses, persist normalized data and audit logs in the primary database.

Key properties
- Reliable: persistent job queue, worker retries with exponential backoff, rate‑limit handling for external providers.
- Idempotent: idempotency keys and dedupe logic prevent duplicated records on retries.
- Observable: audit log entries and job tracing for debugging and replay.
- Configurable: polling intervals, worker concurrency, and provider-specific timeouts are set via environment variables (SYNC_POLL_INTERVAL, WORKER_CONCURRENCY, CONNECTOR_TIMEOUT, NOTIFICATION_WEBHOOK_URL, etc.).

See the diagram in docs/3-tier-sync-loop.mmd for a visual flow of the loop.

---

## ⚙️ Setup

```bash
# Clone the repo
git clone https://github.com/srpihhllc/PlaidBridgeOpenBankingApi.git
cd PlaidBridgeOpenBankingApi

# Create a virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run the app
flask run
