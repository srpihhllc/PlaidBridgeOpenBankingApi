# 📊 Database ERD — Financial Powerhouse Platform

This document describes the relational structure of the platform’s PostgreSQL database.  
It supports compliance workflows, fraud detection, smart contracts, and open banking ingestion.

---

# 🧱 Core Entities

## **Borrower**
- id (PK)
- name
- email
- phone
- risk_score
- created_at

## **Agreement**
- id (PK)
- borrower_id (FK → Borrower)
- content
- ai_flags
- status
- created_at

## **Transaction**
- id (PK)
- borrower_id (FK → Borrower)
- amount
- category
- timestamp
- flagged

## **LinkedAccount**
- id (PK)
- borrower_id (FK → Borrower)
- plaid_account_id
- institution
- status

## **Statement**
- id (PK)
- borrower_id (FK → Borrower)
- pdf_url
- parsed_at

---

# 🔗 Relationships

- Borrower 1‑to‑Many Agreements  
- Borrower 1‑to‑Many Transactions  
- Borrower 1‑to‑Many LinkedAccounts  
- Borrower 1‑to‑Many Statements  

---

# 📐 ERD Diagram (ASCII)

Borrower ───< Agreement
│
├───< Transaction
│
├───< LinkedAccount
│
└───< Statement

Code

---

# 🧩 Notes

- All foreign keys enforce referential integrity.  
- Migrations are managed via Alembic.  
- Admin seed is validated by smoke tests.
