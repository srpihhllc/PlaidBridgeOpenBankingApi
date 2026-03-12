# 📊 Database ERD — Financial Powerhouse Platform
### (PlaidBridgeOpenBankingApi — Backend API & Unified Monorepo)

This document describes the relational structure of the platform’s PostgreSQL database. It supports compliance workflows, fraud detection, smart contracts, and open banking ingestion.

---

**Technical Identity:** `PlaidBridgeOpenBankingApi`  
**Platform Identity:** Financial Powerhouse Platform

---

## 🧱 Core Entities

### Borrower
- id (PK)
- name
- email
- phone
- risk_score
- created_at

### Agreement
- id (PK)
- borrower_id (FK → Borrower.id)
- content
- ai_flags
- status
- created_at

### Transaction
- id (PK)
- borrower_id (FK → Borrower.id)
- amount
- category
- timestamp
- flagged

### LinkedAccount
- id (PK)
- borrower_id (FK → Borrower.id)
- plaid_account_id
- institution
- status

### Statement
- id (PK)
- borrower_id (FK → Borrower.id)
- pdf_url
- parsed_at

---

## 🔗 Relationships

- Borrower 1‑to‑Many Agreements  
- Borrower 1‑to‑Many Transactions  
- Borrower 1‑to‑Many LinkedAccounts  
- Borrower 1‑to‑Many Statements

---

## 📐 ERD Diagram (ASCII)

Borrower ───< Agreement  
│  
├───< Transaction  
│  
├───< LinkedAccount  
│  
└───< Statement

(For a visual diagram, export your schema from PostgreSQL or use a tool like dbdiagram.io / draw.io and place an SVG/PNG at docs/images/database-erd.svg or .png, then reference it here.)

---

## 🧩 Notes & Practices

- All foreign keys enforce referential integrity. Use explicit FK names in migrations to ease debugging.  
- Migrations are managed via Alembic; prefer additive, backward‑compatible migrations where possible (add → backfill → switch → drop).  
- Admin seed is validated by CI smoke tests; ensure the seed validation tests run in your pipeline.  
- Keep model field names and DB column names aligned to avoid mapping confusion.

---

## How to update this document
1. Edit docs/v1/04-database-erd.md with any structural changes.  
2. If you change the schema, add a visual ERD export to docs/images/database-erd.svg (or .png) and reference it here.  
3. Create a PR that includes any Alembic revision(s) and this doc update together to make rollouts traceable.

---
