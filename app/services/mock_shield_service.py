from __future__ import annotations

import base64



import hashlib

import logging

import re

from datetime import datetime, timezone

from decimal import Decimal

from typing import Any



from app.extensions import db

from app.models.bank_account import BankAccount

from app.models.borrower_card import BorrowerCard

from app.models.customer_wallet import CustomerWallet

from app.models.lender import Lender

from app.models.loan import FinancialSnapshot, LoanApplication

from app.models.loan_agreement import LoanAgreement

from app.models.schema_event import SchemaEvent

from app.services.mock_data_service import MockDataService

from app.services.statement_service import generate_statement_pdf



logger = logging.getLogger(__name__)





class ShieldSecurityError(Exception):

    def __init__(self, message: str, code: str = "E_SHIELD", status_code: int = 403):

        super().__init__(message)

        self.message = message

        self.code = code

        self.status_code = status_code





def _emit_shield_event(user_id: str, event_type: str, detail: str, origin: str = "mock_shield") -> None:

    try:

        ev = SchemaEvent(

            user_id=str(user_id),

            event_type=event_type,

            detail=detail[:255],

            origin=origin,

        )

        db.session.add(ev)

    except Exception as exc:

        logger.warning("[mock_shield] SchemaEvent emit skipped: %s", exc)





class MockShieldService:

    @staticmethod

    def assert_lender_kyc_verified(lender_user_id: str) -> Lender:

        lender = Lender.query.filter_by(user_id=str(lender_user_id)).first()

        if not lender:

            raise ShieldSecurityError("Lender profile not found.", "E_LENDER_MISSING", 404)

        required = [

            lender.business_name,

            lender.owner_name,

            lender.ssn_or_ein,

            lender.license_number,

            lender.address,

        ]

        if not all(bool(x and str(x).strip()) for x in required):

            raise ShieldSecurityError("Lender KYC/KYB documentation incomplete.", "E_KYC_INCOMPLETE", 403)

        if not lender.bank_linked:

            raise ShieldSecurityError("Lender bank account must be linked and verified first.", "E_BANK_UNLINKED", 403)

        if lender.verification_status != "verified":

            raise ShieldSecurityError("Lender has not passed Mock Shield KYC verification.", "E_LENDER_UNVERIFIED", 403)

        return lender



    @staticmethod

    def verify_lender_kyc(

        lender_user_id: str,

        photo_id_verified: bool,

        phone_verified: bool,

        bank_linked: bool = True,

    ) -> Lender:

        lender = Lender.query.filter_by(user_id=str(lender_user_id)).first()

        if not lender:

            raise ShieldSecurityError("Lender profile not found.", "E_LENDER_MISSING", 404)

        if not (photo_id_verified and phone_verified and bank_linked):

            lender.verification_status = "rejected"

            db.session.commit()

            raise ShieldSecurityError(

                "Photo ID, verified phone, and linked bank account are mandatory.",

                "E_KYC_FAILED",

                403,

            )

        lender.bank_linked = True

        lender.linked_at = datetime.now(timezone.utc)

        lender.verification_status = "verified"

        lender.verification_score = max(int(lender.verification_score or 0), 95)

        _emit_shield_event(lender_user_id, "SHIELD_LENDER_KYC_VERIFIED", f"Lender {lender.id} verified")

        db.session.commit()

        return lender



    @staticmethod

    def issue_scoped_proxy_snapshot(

        lender_user_id: str,

        application_id: int,

        requested_fields: list[str] | None = None,

    ) -> dict[str, Any]:

        lender = MockShieldService.assert_lender_kyc_verified(lender_user_id)

        app_rec = LoanApplication.query.filter_by(

            id=application_id, lender_id=str(lender_user_id)

        ).first()

        if not app_rec:

            raise ShieldSecurityError("Loan application not found for lender.", "E_APP_NOT_FOUND", 404)

        if not app_rec.subscriber_consent_at or app_rec.access_revoked_at is not None:

            raise ShieldSecurityError(

                "Subscriber consent missing or revoked; proxy blocked.",

                "E_CONSENT_REQUIRED",

                403,

            )



        allowed_scopes = {"balance_summary", "cashflow_30d", "baas_statement_pdf"}

        scopes = set(requested_fields or allowed_scopes) & allowed_scopes



        acct_meta = MockDataService.generate_mock_account_metadata(app_rec.subscriber_id)

        balance = MockDataService.generate_mock_balance()

        txns = MockDataService.generate_mock_transactions(days=30)

        analytics = MockDataService.generate_mock_analytics(txns)



        scoped_payload: dict[str, Any] = {

            "proxy_mode": "zero_trust_shield",

            "institution_mask": acct_meta.get("institution_name", "Verified Institution"),

            "account_mask": acct_meta.get("mask", "****"),

        }

        if "balance_summary" in scopes:

            scoped_payload["balances"] = {

                "available": balance.get("available"),

                "current": balance.get("current"),

                "currency": balance.get("iso_currency_code", "USD"),

            }

        if "cashflow_30d" in scopes:

            scoped_payload["analytics"] = analytics



        pdf_b64 = None

        if "baas_statement_pdf" in scopes:

            pdf_bytes = generate_statement_pdf(user_id=app_rec.subscriber_id, lender_id=lender.id)

            pdf_b64 = base64.b64encode(pdf_bytes).decode("utf-8")



        snap = FinancialSnapshot(

            application_id=app_rec.id,

            subscriber_id=str(app_rec.subscriber_id),

            loan_review_data=scoped_payload,

        )

        db.session.add(snap)

        _emit_shield_event(

            app_rec.subscriber_id,

            "SHIELD_SCOPED_PROXY_ISSUED",

            f"Scoped snapshot {snap.id} issued to lender {lender.id}",

        )

        db.session.commit()



        result = {"snapshot_id": snap.id, "loan_review_data": scoped_payload}

        if pdf_b64 is not None:

            result["watermarked_statement_pdf_base64"] = pdf_b64

        return result



    @staticmethod

    def evaluate_loan_agreement(

        lender_user_id: str,

        borrower_id: str,

        terms: str,

        apr_percent: float = 0.0,

        origination_fee_percent: float = 0.0,

        unilateral_sweep: bool = False,

    ) -> LoanAgreement:

        lender = MockShieldService.assert_lender_kyc_verified(lender_user_id)

        lowered = (terms or "").lower()

        predatory_reasons: list[str] = []



        if apr_percent > 36.0:

            predatory_reasons.append(f"APR {apr_percent}% exceeds 36% cap")

        if origination_fee_percent > 10.0:

            predatory_reasons.append(f"Origination fee {origination_fee_percent}% exceeds 10% cap")

        if unilateral_sweep or "unilateral sweep" in lowered or "blanket ach" in lowered:

            predatory_reasons.append("Unilateral full-balance sweep clause prohibited")

        if re.search(r"confession of judgment|waive all rights", lowered):

            predatory_reasons.append("Predatory waiver / confession-of-judgment clause")



        is_predatory = len(predatory_reasons) > 0

        agreement = LoanAgreement(

            lender_id=str(lender_user_id),

            borrower_id=str(borrower_id),

            terms=terms,

            status="rejected_predatory" if is_predatory else "approved_pending_disclosure",

            ai_flagged=is_predatory,

            locked=False,

            violation_count=1 if is_predatory else 0,

        )

        db.session.add(agreement)



        if is_predatory:

            _emit_shield_event(

                lender_user_id,

                "PREDATORY_AGREEMENT_BLOCKED",

                f"Lender {lender.id} flagged: {"; ".join(predatory_reasons)}",

            )

            try:

                from app.utils import notify_authorities

                notify_authorities(

                    "Predatory Loan Agreement Blocked",

                    {

                        "lender_id": lender.id,

                        "borrower_id": borrower_id,

                        "reasons": predatory_reasons,

                    },

                )

            except Exception as exc:

                logger.warning("[mock_shield] notify_authorities skipped: %s", exc)

            db.session.commit()

            raise ShieldSecurityError(

                f"Predatory loan agreement rejected and reported: {"; ".join(predatory_reasons)}",

                "E_PREDATORY_LOAN",

                403,

            )



        _emit_shield_event(

            borrower_id,

            "LOAN_AGREEMENT_CLEARED",

            f"Agreement cleared by AI audit for lender {lender.id}",

        )

        db.session.commit()

        return agreement



    @staticmethod

    def sign_borrower_disclosure(

        borrower_id: str,

        agreement_id: int,

        acknowledged_rules: bool,

        signature_text: str,

    ) -> LoanAgreement:

        agreement = LoanAgreement.query.filter_by(

            id=agreement_id, borrower_id=str(borrower_id)

        ).first()

        if not agreement:

            raise ShieldSecurityError("Loan agreement not found.", "E_AGREEMENT_MISSING", 404)

        if agreement.ai_flagged or agreement.status == "rejected_predatory":

            raise ShieldSecurityError("Cannot sign a flagged predatory agreement.", "E_PREDATORY_LOAN", 403)

        if not acknowledged_rules or not (signature_text and signature_text.strip()):

            raise ShieldSecurityError(

                "Borrower must acknowledge Mock Shield rules and sign before disbursement.",

                "E_DISCLOSURE_REQUIRED",

                403,

            )



        sig_hash = hashlib.sha256(

            f"{agreement.id}|{borrower_id}|{signature_text.strip()}".encode("utf-8")

        ).hexdigest()[:16]

        agreement.status = "disclosure_signed"

        _emit_shield_event(

            borrower_id,

            "BORROWER_DISCLOSURE_SIGNED",

            f"Agreement {agreement.id} signed (sig={sig_hash})",

        )

        db.session.commit()

        return agreement



    @staticmethod

    def disburse_escrowed_loan(

        lender_user_id: str,

        agreement_id: int,

        principal_amount: Decimal | float | str,

    ) -> dict[str, Any]:

        MockShieldService.assert_lender_kyc_verified(lender_user_id)

        agreement = LoanAgreement.query.filter_by(

            id=agreement_id, lender_id=str(lender_user_id)

        ).first()

        if not agreement:

            raise ShieldSecurityError("Loan agreement not found.", "E_AGREEMENT_MISSING", 404)

        if agreement.ai_flagged:

            raise ShieldSecurityError("Predatory agreement blocked from disbursement.", "E_PREDATORY_LOAN", 403)

        if agreement.status != "disclosure_signed":

            raise ShieldSecurityError(

                "Borrower rules & regulations disclosure must be signed prior to fund transfer.",

                "E_DISCLOSURE_UNSIGNED",

                403,

            )



        amt = Decimal(str(principal_amount))

        if amt <= Decimal("0.00"):

            raise ShieldSecurityError("Disbursement amount must be positive.", "E_INVALID_AMOUNT", 400)



        wallet = CustomerWallet.query.filter_by(user_id=agreement.borrower_id).first()

        if not wallet:

            wallet = CustomerWallet(user_id=agreement.borrower_id, balance=Decimal("0.00"))

            db.session.add(wallet)



        wallet.balance = Decimal(str(wallet.balance or "0.00")) + amt

        agreement.locked = True

        agreement.status = "active_escrow"



        for acct in BankAccount.query.filter_by(user_id=str(agreement.borrower_id)).all():

            acct.trace_status = "escrow_locked"



        _emit_shield_event(

            agreement.borrower_id,

            "ESCROW_LOAN_DISBURSED",

            f"Disbursed {amt} under locked agreement {agreement.id}",

        )

        db.session.commit()

        return {

            "agreement_id": agreement.id,

            "status": agreement.status,

            "locked": agreement.locked,

            "credited_amount": str(amt),

            "wallet_balance": str(wallet.balance),

        }



    @staticmethod

    def guard_lender_debit(

        lender_user_id: str,

        agreement_id: int,

        requested_debit: Decimal | float | str,

        authorized_installment: Decimal | float | str,

    ) -> dict[str, Any]:

        agreement = LoanAgreement.query.filter_by(

            id=agreement_id, lender_id=str(lender_user_id)

        ).first()

        if not agreement:

            raise ShieldSecurityError("Loan agreement not found.", "E_AGREEMENT_MISSING", 404)



        debit = Decimal(str(requested_debit))

        cap = Decimal(str(authorized_installment))

        wallet = CustomerWallet.query.filter_by(user_id=agreement.borrower_id).first()

        bal = Decimal(str(wallet.balance if wallet else "0.00"))



        if debit > cap or debit >= bal:

            agreement.violation_count = int(agreement.violation_count or 0) + 1

            _emit_shield_event(

                agreement.borrower_id,

                "SHIELD_EXCESS_WITHDRAWAL_BLOCKED",

                f"Blocked lender debit {debit} (cap={cap}, bal={bal}) on agreement {agreement.id}",

            )

            db.session.commit()

            raise ShieldSecurityError(

                "Unauthorized or full-balance lender withdrawal blocked by Mock Shield.",

                "E_PREDATORY_SWEEP_BLOCKED",

                403,

            )



        return {"allowed": True, "approved_debit": str(debit)}



    @staticmethod

    def enforce_loan_default(

        agreement_id: int,

        full_default: bool = True,

    ) -> dict[str, Any]:

        agreement = db.session.get(LoanAgreement, agreement_id)

        if not agreement:

            raise ShieldSecurityError("Loan agreement not found.", "E_AGREEMENT_MISSING", 404)



        wallet = CustomerWallet.query.filter_by(user_id=agreement.borrower_id).first()

        clawback = Decimal("0.00")

        if wallet:

            wallet.is_frozen = True

            wallet.status = "frozen_default" if full_default else "frozen_delinquent"

            if full_default:

                clawback = Decimal(str(wallet.balance or "0.00"))

                wallet.balance = Decimal("0.00")



        cards = BorrowerCard.query.filter_by(user_id=str(agreement.borrower_id)).all()

        for card in cards:

            card.revoked = True

            card.trace_status = "frozen_default" if full_default else "frozen_delinquent"



        agreement.locked = True

        agreement.status = "defaulted_clawback" if full_default else "delinquent_frozen"



        _emit_shield_event(

            agreement.borrower_id,

            "BORROWER_DEFAULT_ENFORCED" if full_default else "BORROWER_CARD_FROZEN",

            f"Agreement {agreement.id}: clawback={clawback}, full_default={full_default}",

        )

        db.session.commit()

        return {

            "agreement_id": agreement.id,

            "status": agreement.status,

            "wallet_frozen": True,

            "cards_frozen": len(cards),

            "clawback_returned_to_lender": str(clawback),

        }

