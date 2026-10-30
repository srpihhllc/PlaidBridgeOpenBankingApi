from flask import Blueprint
from flask import request
from flask import jsonify

from app.services.transfer_engine import (
    TransferEngine,
)

banking_bp = Blueprint(
    "banking",
    __name__,
)


@banking_bp.post("/api/v1/banking/transfer")
def transfer():
    payload = request.get_json()

    result = TransferEngine.transfer(
        idempotency_key=payload["idempotency_key"],
        debit_account_id=payload["debit_account_id"],
        credit_account_id=payload["credit_account_id"],
        amount=payload["amount"],
    )

    return jsonify(result)