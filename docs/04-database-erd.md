# 📊 Database ERD — Financial Powerhouse Platform

This document describes the relational structure of the platform’s PostgreSQL database.  
It supports compliance workflows, fraud detection, smart contracts, and open banking ingestion.

---

## Overview
This ERD summarizes the core entities used across the backend services (compliance engine, fraud detection, open banking ingestion, etc.). Migrations are managed via Alembic and all foreign keys enforce referential integrity.

Technical Identity: `PlaidBridgeOpenBankingApi`  
Platform Identity: Financial Powerhouse Platform

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
- Borrower 1-to-Many Agreements  
- Borrower 1-to-Many Transactions  
- Borrower 1-to-Many LinkedAccounts  
- Borrower 1-to-Many Statements  

---

## 📐 ERD Diagram (ASCII)

Borrower ───< Agreement
│
├───< Transaction
│
├───< LinkedAccount
│
└───< Statement

(For a visual diagram, export your schema from PostgreSQL or use a tool like dbdiagram.io / draw.io and store an SVG/PNG at docs/images/database-erd.png.)

---

## 🧩 Notes & Practices
- All foreign keys enforce referential integrity. Use explicit FK names in migrations to ease debugging.
- Use Alembic for schema migrations. Prefer additive, backward-compatible migrations where possible (add columns, backfill, then remove legacy code).
- Ensure admin seed validation is covered by CI smoke tests (see tests/ for seed validation tests).
- Keep model-field names and database column names aligned to avoid mapping confusion.

---

## How to update this document
1. Edit docs/04-database-erd.md with any structural changes.  
2. If you change the schema, add a visual ERD export to docs/images/database-erd.png or .svg and reference it here.  
3. Create a short PR describing the migration (alembic revision) and update this doc in the same PR.

---
