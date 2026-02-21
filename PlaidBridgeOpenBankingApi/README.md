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


