# Lending Sync Strategy

## 📚 Overview

This strategy defines how credit events inside the platform (e.g. card issuance, borrower repayments) are aligned with external lending flows from outside funders. It establishes unified traceability across `credit_ledger`, `payment_log`, `loan_agreement`, and webhooks.

---

## 💳 Internal Lending Flow (API-Issued Credit)

- Borrowers are issued virtual credit cards
- Card activity tracked in `credit_ledger`
- Repayments logged in `payment_log`
- Treasury Prime webhooks update `credit_limit`, balance, or card status

---

## 💰 External Lending Flow (Outside Lenders → Borrowers)

- Loans tracked via `loan_agreement`
- Repayments also logged in `payment_log`
- AI traces map fund source and compliance
- `fraud_reports` flag anomalies or abuse

---

## 🔄 Unified Structure in `payment_log`

| Field        | Description                          |
|--------------|--------------------------------------|
| `id`         | Primary key                          |
| `card_id`    | May be null for non-card repayments  |
| `user_id`    | Borrower identifier                  |
| `amount`     | Payment value                        |
| `timestamp`  | When repayment occurred              |
| `source_type`| `'internal_card'` or `'external_lender'` |

---

## ✅ Next Steps

- Tag all payments with `source_type`
- Wire `loan_id` as foreign key (optional)
- Build reconciliation engine to compare:
  - `credit_ledger.credit_limit` vs repayment sum
  - Missed repayments vs active loans
- Push violations into `fraud_reports` if thresholds breached
