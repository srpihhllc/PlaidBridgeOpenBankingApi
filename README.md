# Financial Powerhouse Platform
### (PlaidBridgeOpenBankingApi — Unified Fintech Monorepo)

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

✅ 2. GitHub Pages Deployment Workflow
Create this file:

Code
.github/workflows/docs.yml
yaml
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
✔ What this gives you
Automatic docs deployment on every push to main

Manual deploy via “Run workflow”

MkDocs Material theme

Fully version‑controlled documentation site

✅ 3. Combined PDF‑Ready Manual
Create this file:

Code
docs/manual.md
This is a single unified manual that can be exported to PDF using MkDocs or Pandoc.

markdown
# 📘 Financial Powerhouse Platform — Complete Technical Manual

This manual consolidates all core documentation for the Financial Powerhouse Platform, including architecture, backend design, mobile architecture, ERD, CI/CD, operator workflows, and API reference.

---

# 1. System Architecture
(From `01-system-architecture.md`)
---

# 2. Backend Architecture
(From `03-backend-architecture.md`)
---

# 3. Database ERD
(From `04-database-erd.md`)
---

# 4. Developer Onboarding
(From `05-developer-onboarding.md`)
---

# 5. CI/CD Pipeline
(From `06-ci-cd-pipeline.md`)
---

# 6. Operator Handbook
(From `07-operator-handbook.md`)
---

# 7. Release Notes
(From `08-release-notes.md`)
---

# 8. API Reference
(From `09-api-reference.md`)
---

# 9. OpenAPI Specification

```yaml
# From 10-openapi.yaml
10. Monorepo Architecture Diagram
(From 11-monorepo-architecture-diagram.md)

11. Mobile Architecture
(From 12-mobile-architecture.md)

🎉 End of Manual
Code

### ✔ Export to PDF

Using MkDocs:

mkdocs build

Code

Using Pandoc:

pandoc docs/manual.md -o FinancialPowerhouseManual.pdf

Code

---

# ⭐ Documentation suite is now complete:

### ✔ Full docs index  
### ✔ Full docs suite  
### ✔ GitHub Pages deployment  
### ✔ PDF‑ready manual  
### ✔ MkDocs site config  
### ✔ Backend README  
### ✔ Mobile architecture  
### ✔ Operator handbook  
### ✔ CI/CD docs  
### ✔ ERD  
### ✔ API reference  
### ✔ OpenAPI spec  
