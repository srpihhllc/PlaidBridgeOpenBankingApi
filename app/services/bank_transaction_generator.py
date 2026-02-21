# =============================================================================
# FILE: app/services/bank_transaction_generator.py
# DESCRIPTION: Generates realistic mock ACH, Wire, and Internal transfers for
#              BankTransaction. Produces routing numbers, trace numbers,
#              SEC codes, wire references, timestamps, and payment channels.
# =============================================================================

import random
from datetime import datetime, timedelta

from app.extensions import db
from app.models import BankAccount, BankTransaction

ACH_SEC_CODES = ["PPD", "CCD", "WEB", "TEL"]
PAYMENT_CHANNELS = ["ACH", "WIRE", "INTERNAL"]


def _random_routing_number():
    return "".join(str(random.randint(0, 9)) for _ in range(9))


def _random_ach_trace():
    return "".join(str(random.randint(0, 9)) for _ in range(15))


def _random_wire_reference():
    return f"WR-{random.randint(1000000, 9999999)}"


def generate_mock_bank_transfer(from_account, to_account, days_back=30):
    """
    Generate a single realistic ACH/Wire/Internal BankTransaction object.
    Does NOT commit to the DB — caller decides when to commit.
    """

    payment_channel = random.choice(PAYMENT_CHANNELS)

    # Channel-specific metadata
    if payment_channel == "ACH":
        txn_type = "ach"
        ach_sec_code = random.choice(ACH_SEC_CODES)
        wire_reference = None
        ach_trace_number = _random_ach_trace()

    elif payment_channel == "WIRE":
        txn_type = "wire"
        ach_sec_code = None
        wire_reference = _random_wire_reference()
        ach_trace_number = None

    else:  # INTERNAL
        txn_type = "internal"
        ach_sec_code = None
        wire_reference = None
        ach_trace_number = None

    amount = round(random.uniform(25, 2500), 2)
    timestamp = datetime.utcnow() - timedelta(days=random.randint(0, days_back))

    txn = BankTransaction(
        from_account_id=from_account.id if from_account else None,
        to_account_id=to_account.id if to_account else None,
        amount=amount,
        txn_type=txn_type,
        method=random.choice(["online", "teller", "mobile"]),
        timestamp=timestamp,
        ach_trace_number=ach_trace_number,
        ach_sec_code=ach_sec_code,
        wire_reference=wire_reference,
        originating_routing=(
            _random_routing_number() if payment_channel in ("ACH", "WIRE") else None
        ),
        receiving_routing=(
            _random_routing_number() if payment_channel in ("ACH", "WIRE") else None
        ),
        payment_channel=payment_channel,
    )

    return txn


def seed_mock_bank_transfers_for_user(user, count=20):
    """
    Create and commit a batch of mock transfers for all of a user's accounts.
    Returns the number of transfers created.
    """

    accounts = BankAccount.query.filter_by(user_id=user.id).all()
    if not accounts:
        return 0

    for _ in range(count):
        from_account = random.choice(accounts)
        to_account = random.choice(accounts)

        # Allow external transfers by occasionally nulling the destination
        if from_account.id == to_account.id:
            to_account = None

        txn = generate_mock_bank_transfer(from_account, to_account)
        db.session.add(txn)

    db.session.commit()
    return count
