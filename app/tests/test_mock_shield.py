from datetime import datetime, timezone

from decimal import Decimal

import pytest



from app import create_app

from app.config import TestingConfig

from app.extensions import db

from app.models.borrower_card import BorrowerCard

from app.models.customer_wallet import CustomerWallet

from app.models.lender import Lender

from app.models.loan import LoanApplication

from app.models.user import User

from app.services.mock_shield_service import MockShieldService, ShieldSecurityError





@pytest.fixture

def shield_ctx():

    app = create_app(config_class=TestingConfig)

    with app.app_context():

        db.create_all()

        lender_user = User(

            id="lender-user-001",

            username="apex_lender",

            email="lender@apex.example.com",

            role="lender",

        )

        lender_user.set_password("StrongPass!123")

        borrower_user = User(

            id="borrower-user-001",

            username="jane_borrower",

            email="jane@borrower.example.com",

            role="subscriber",

        )

        borrower_user.set_password("StrongPass!123")

        db.session.add_all([lender_user, borrower_user])

        db.session.flush()



        lender = Lender(

            user_id=lender_user.id,

            business_name="Apex Capital LLC",

            owner_name="Marcus Vance",

            ssn_or_ein="12-3456789",

            license_number="LIC-TN-9981",

            address="100 Main St, Memphis, TN",

            institution_name="Apex Bank",

            verification_status="pending",

            bank_linked=False,

        )

        db.session.add(lender)

        db.session.commit()

        yield app, lender_user, borrower_user, lender

        db.session.remove()

        db.drop_all()





def test_full_mock_shield_lifecycle(shield_ctx):

    _, lender_user, borrower_user, _ = shield_ctx



    # 1. Unverified lender is blocked before KYC

    with pytest.raises(ShieldSecurityError) as exc_unverified:

        MockShieldService.assert_lender_kyc_verified(lender_user.id)

    assert exc_unverified.value.status_code == 403



    # 2. Verify lender KYC (Photo ID + Phone + Bank Linked)

    verified = MockShieldService.verify_lender_kyc(

        lender_user_id=lender_user.id,

        photo_id_verified=True,

        phone_verified=True,

        bank_linked=True,

    )

    assert verified.verification_status == "verified"



    # 3. Scoped virtual proxy requires explicit borrower consent

    loan_app = LoanApplication(

        lender_id=lender_user.id,

        subscriber_id=borrower_user.id,

        requested_amount=Decimal("5000.00"),

        purpose="Working capital",

        status="approved",

        subscriber_consent_at=datetime.now(timezone.utc),

    )

    db.session.add(loan_app)

    db.session.commit()



    proxy = MockShieldService.issue_scoped_proxy_snapshot(

        lender_user_id=lender_user.id,

        application_id=loan_app.id,

        requested_fields=["balance_summary", "baas_statement_pdf"],

    )

    assert proxy["loan_review_data"]["proxy_mode"] == "zero_trust_shield"

    assert "watermarked_statement_pdf_base64" in proxy



    # 4. AI predatory loan check blocks >36% APR or unilateral sweep

    with pytest.raises(ShieldSecurityError) as exc_pred:

        MockShieldService.evaluate_loan_agreement(

            lender_user_id=lender_user.id,

            borrower_id=borrower_user.id,

            terms="Standard note with unilateral sweep clause",

            apr_percent=49.9,

            unilateral_sweep=True,

        )

    assert exc_pred.value.code == "E_PREDATORY_LOAN"



    # 5. Clean agreement clears AI audit, but disbursement blocks until borrower signs disclosure

    clean_ag = MockShieldService.evaluate_loan_agreement(

        lender_user_id=lender_user.id,

        borrower_id=borrower_user.id,

        terms="Fixed 12-month installment note at 14.5% APR",

        apr_percent=14.5,

        origination_fee_percent=2.0,

    )

    assert clean_ag.status == "approved_pending_disclosure"



    with pytest.raises(ShieldSecurityError) as exc_unsigned:

        MockShieldService.disburse_escrowed_loan(

            lender_user_id=lender_user.id,

            agreement_id=clean_ag.id,

            principal_amount="5000.00",

        )

    assert exc_unsigned.value.code == "E_DISCLOSURE_UNSIGNED"



    # 6. Borrower signs disclosure -> immediate escrow disbursement locks agreement & credits wallet

    signed_ag = MockShieldService.sign_borrower_disclosure(

        borrower_id=borrower_user.id,

        agreement_id=clean_ag.id,

        acknowledged_rules=True,

        signature_text="Jane Borrower /s/",

    )

    assert signed_ag.status == "disclosure_signed"



    disb = MockShieldService.disburse_escrowed_loan(

        lender_user_id=lender_user.id,

        agreement_id=clean_ag.id,

        principal_amount="5000.00",

    )

    assert disb["locked"] is True

    assert Decimal(disb["wallet_balance"]) == Decimal("5000.00")



    # 7. Anti-sweep guard blocks lender withdrawal exceeding authorized installment

    with pytest.raises(ShieldSecurityError) as exc_sweep:

        MockShieldService.guard_lender_debit(

            lender_user_id=lender_user.id,

            agreement_id=clean_ag.id,

            requested_debit="5000.00",

            authorized_installment="450.00",

        )

    assert exc_sweep.value.code == "E_PREDATORY_SWEEP_BLOCKED"



    # 8. Default enforcement freezes wallet & card and claws back unused funds

    card = BorrowerCard(

        user_id=borrower_user.id,

        card_number="4111222233334444",

        expiration_date="12/29",

        cvv="999",

        score=720,

        color="black",

    )

    db.session.add(card)

    db.session.commit()



    default_res = MockShieldService.enforce_loan_default(agreement_id=clean_ag.id, full_default=True)

    assert default_res["wallet_frozen"] is True

    assert Decimal(default_res["clawback_returned_to_lender"]) == Decimal("5000.00")

    wallet = CustomerWallet.query.filter_by(user_id=borrower_user.id).first()

    assert wallet.is_frozen is True

    assert Decimal(wallet.balance) == Decimal("0.00")

