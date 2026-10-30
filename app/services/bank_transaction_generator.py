# =============================================================================
# FILE: app/services/bank_transaction_generator.py
# DESCRIPTION: Generates realistic mock ACH, Wire, and Internal transfers for
#              BankTransaction. Produces routing numbers, trace numbers, SEC
#              codes, wire references, timestamps, and payment channels.
# =============================================================================

import random
from datetime import datetime, timedelta, timezone

from app.extensions import db
from app.models import BankAccount, BankTransaction

ACH_SEC_CODES = ("PPD", "CCD", "WEB", "TEL")
PAYMENT_CHANNELS = ("ACH", "WIRE", "INTERNAL")
TRANSFER_METHODS = ("online", "teller", "mobile")


def _random_routing_number():
    """Return a nine-digit routing number with a valid ABA checksum."""
    first_eight = [random.randint(0, 9) for _ in range(8)]

    # ABA routing numbers begin with 0, 1, 2, or 3.
    first_eight[0] = random.randint(0, 3)

    checksum_total = sum(
        digit * weight
        for digit, weight in zip(first_eight, (3, 7, 1, 3, 7, 1, 3, 7))
    )
    check_digit = (-checksum_total) % 10

    return "".join(map(str, first_eight)) + str(check_digit)


def _random_ach_trace():
    """Return a 15-digit mock ACH trace number."""
    return "".join(str(random.randint(0, 9)) for _ in range(15))


def _random_wire_reference():
    """Return a mock wire reference."""
    return f"WR-{random.randint(1_000_000, 9_999_999)}"


def generate_mock_bank_transfer(from_account, to_account, days_back=30):
    """
    Generate a mock ACH, wire, or internal BankTransaction.

    The transaction is added to the returned object but is not added to the
    database session or committed. The caller controls persistence.
    """
    if not isinstance(days_back, int) or days_back < 0:
        raise ValueError("days_back must be a non-negative integer")

    payment_channel = random.choice(PAYMENT_CHANNELS)

    ach_sec_code = None
    ach_trace_number = None
    wire_reference = None

    if payment_channel == "ACH":
        txn_type = "ach"
        ach_sec_code = random.choice(ACH_SEC_CODES)
        ach_trace_number = _random_ach_trace()
    elif payment_channel == "WIRE":
        txn_type = "wire"
        wire_reference = _random_wire_reference()
    else:
        txn_type = "internal"

    timestamp = datetime.now(timezone.utc) - timedelta(
        days=random.randint(0, days_back)
    )

    return BankTransaction(
        from_account_id=from_account.id if from_account else None,
        to_account_id=to_account.id if to_account else None,
        amount=round(random.uniform(25, 2500), 2),
        txn_type=txn_type,
        method=random.choice(TRANSFER_METHODS),
        timestamp=timestamp,
        ach_trace_number=ach_trace_number,
        ach_sec_code=ach_sec_code,
        wire_reference=wire_reference,
        originating_routing=(
            _random_routing_number()
            if payment_channel in ("ACH", "WIRE")
            else None
        ),
        receiving_routing=(
            _random_routing_number()
            if payment_channel in ("ACH", "WIRE")
            else None
        ),
        payment_channel=payment_channel,
    )


def seed_mock_bank_transfers_for_user(user, count=20):
    """
    Create and commit mock transfers for a user's accounts.

    Returns the number of transfers created. If the database operation fails,
    the session is rolled back and the exception is propagated.
    """
    if not isinstance(count, int) or count < 0:
        raise ValueError("count must be a non-negative integer")

    accounts = BankAccount.query.filter_by(user_id=user.id).all()
    if not accounts or count == 0:
        return 0

    try:
        for _ in range(count):
            from_account = random.choice(accounts)

            # Prefer a different account when one is available. With only one
            # account, use a null destination to represent an external transfer.
            other_accounts = [
                account for account in accounts
                if account.id != from_account.id
            ]
            to_account = (
                random.choice(other_accounts)
                if other_accounts
                else None
            )

            txn = generate_mock_bank_transfer(from_account, to_account)
            db.session.add(txn)

        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    return count