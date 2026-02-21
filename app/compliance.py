# app/compliance.py


from app.extensions import db
from app.models import (
    FinancialAuditLog,  # Added FinancialAuditLog
    LoanAgreement,
    User,
)


def check_lender_compliance(lender_id):
    """
    Checks if a lender follows ethical loan agreements.
    If predatory patterns are found, it logs a violation and enforces a lock.
    """
    lender = db.session.get(User, lender_id)
    if not lender:
        return {"error": "Lender not found"}

    lender_agreements = LoanAgreement.query.filter_by(lender_id=lender_id).all()

    # Logic: Identify "Bad" agreements (e.g., those with internal violation flags)
    current_violations = [a for a in lender_agreements if getattr(a, "violation_count", 0) > 0]

    if current_violations:
        for v in current_violations:
            # 1. Update the User's aggregate violation count
            lender.violation_count += 1

            # 2. Log to the new FinancialAuditLog table
            audit = FinancialAuditLog(
                actor_id=lender.id,
                action_type="VIOLATION_LOGGED",
                description=f"Agreement ID {v.id} flagged for compliance violation.",
            )
            db.session.add(audit)

    # 3. Strike 3 Rule: Automatic Lockout
    if lender.violation_count >= 3 and not lender.is_locked:
        lender.is_locked = True
        lender.lock_reason = "Automated Lock: Exceeded 3 compliance violations."

        lock_audit = FinancialAuditLog(
            actor_id=lender.id,
            action_type="ACCOUNT_LOCKED",
            description="Lender account locked due to repeated predatory patterns.",
        )
        db.session.add(lock_audit)

    db.session.commit()

    return {
        "lender_id": lender_id,
        "violations_total": lender.violation_count,
        "is_locked": lender.is_locked,
        "total_agreements": len(lender_agreements),
    }


# Inside generate_compliance_report
lender_compliance = {
    lender.id: check_lender_compliance(lender.id)
    for lender in User.query.filter(
        (User.role == "lender")
        | (User.is_admin.is_(False))  # Or any logic that excludes non-participants
    ).all()
    if lender.lent_loan_agreements.count() > 0
}
