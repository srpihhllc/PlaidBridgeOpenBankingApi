# =============================================================================

# FILE: app/blueprints/banking_routes.py

# DESCRIPTION: Unified Banking, Multi-Rail Payments (ACH/FedNow/RTP), Wallet,

#              and Double-Entry Reconciliation API blueprint.

# =============================================================================



from __future__ import annotations



import logging

from decimal import Decimal, InvalidOperation

from functools import wraps



from flask import Blueprint, current_app, jsonify, request

from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request

from flask_login import current_user



from app.extensions import db

from app.models.customer_wallet import CustomerWallet

from app.services.ach_engine import ACHEngine, ACHEngineError

from app.services.fednow_engine import FedNowEngine, FedNowError

from app.services.reconciliation_engine import ReconciliationEngine, ReconciliationError

from app.services.rtp_engine import RTPEngine, RTPError

from app.services.transfer_engine import TransferEngine

from app.services.wallet_engine import WalletEngine, WalletError



logger = logging.getLogger(__name__)



banking_bp = Blueprint("banking", __name__)





def _require_banking_auth(fn):

    @wraps(fn)

    def wrapper(*args, **kwargs):

        if current_app.config.get("TESTING"):

            return fn(*args, **kwargs)

        verify_jwt_in_request(optional=True)

        if get_jwt_identity() is not None or getattr(current_user, "is_authenticated", False):

            return fn(*args, **kwargs)

        return jsonify({"status": "error", "message": "Authentication required."}), 401

    return wrapper





def _parse_decimal(val) -> Decimal:

    try:

        return Decimal(str(val))

    except (InvalidOperation, TypeError, ValueError) as exc:

        raise ValueError(f"Invalid monetary amount: {val!r}") from exc





def _serialize_instruction(inst) -> dict:

    return {

        "id": getattr(inst, "id", None),

        "payment_type": str(getattr(inst, "payment_type", "")),

        "status": str(getattr(inst, "status", "")),

        "debit_wallet_id": getattr(inst, "debit_wallet_id", None),

        "credit_wallet_id": getattr(inst, "credit_wallet_id", None),

        "amount": str(getattr(inst, "amount", "0.00")),

        "idempotency_key": getattr(inst, "idempotency_key", None),

        "memo": getattr(inst, "memo", None),

    }





@banking_bp.post("/api/v1/banking/transfer")

@_require_banking_auth

def transfer():

    payload = request.get_json(silent=True) or {}

    result = TransferEngine.transfer(

        idempotency_key=payload["idempotency_key"],

        debit_account_id=payload["debit_account_id"],

        credit_account_id=payload["credit_account_id"],

        amount=payload["amount"],

    )

    return jsonify(result)





# -----------------------------------------------------------------------------

# ACH Rail Endpoints

# -----------------------------------------------------------------------------

@banking_bp.post("/api/v1/banking/ach/transfers")

@_require_banking_auth

def create_ach_transfer():

    payload = request.get_json(silent=True) or {}

    try:

        inst = ACHEngine.create_transfer(

            debit_wallet_id=int(payload["debit_wallet_id"]),

            credit_wallet_id=int(payload["credit_wallet_id"]),

            amount=_parse_decimal(payload["amount"]),

            idempotency_key=str(payload["idempotency_key"]),

            memo=payload.get("memo"),

            created_by=payload.get("created_by"),

        )

        return jsonify({"status": "success", "instruction": _serialize_instruction(inst)}), 201

    except (KeyError, ValueError, ACHEngineError) as err:

        return jsonify({"status": "error", "message": str(err)}), 400





@banking_bp.post("/api/v1/banking/ach/batches")

@_require_banking_auth

def build_ach_batch():

    payload = request.get_json(silent=True) or {}

    try:

        batch = ACHEngine.build_settlement_batch(

            payment_type=payload.get("payment_type", "ach"),

            created_by=payload.get("created_by"),

        )

        return jsonify({"status": "success", "batch_id": getattr(batch, "id", None)}), 201

    except ACHEngineError as err:

        return jsonify({"status": "error", "message": str(err)}), 400





# -----------------------------------------------------------------------------

# FedNow Real-Time Rail Endpoints

# -----------------------------------------------------------------------------

@banking_bp.post("/api/v1/banking/fednow/transfers")

@_require_banking_auth

def create_fednow_transfer():

    payload = request.get_json(silent=True) or {}

    try:

        inst = FedNowEngine.create_transfer(

            debit_wallet_id=int(payload["debit_wallet_id"]),

            credit_wallet_id=int(payload["credit_wallet_id"]),

            amount=_parse_decimal(payload["amount"]),

            idempotency_key=str(payload["idempotency_key"]),

            memo=payload.get("memo"),

            created_by=payload.get("created_by"),

        )

        if payload.get("auto_process", True):

            inst = FedNowEngine.process(inst)

        return jsonify({"status": "success", "instruction": _serialize_instruction(inst)}), 201

    except (KeyError, ValueError, FedNowError) as err:

        return jsonify({"status": "error", "message": str(err)}), 400





@banking_bp.get("/api/v1/banking/fednow/health")

@_require_banking_auth

def fednow_health():

    return jsonify(FedNowEngine.healthcheck()), 200





# -----------------------------------------------------------------------------

# RTP Real-Time Rail Endpoints

# -----------------------------------------------------------------------------

@banking_bp.post("/api/v1/banking/rtp/transfers")

@_require_banking_auth

def create_rtp_transfer():

    payload = request.get_json(silent=True) or {}

    try:

        inst = RTPEngine.create_transfer(

            debit_wallet_id=int(payload["debit_wallet_id"]),

            credit_wallet_id=int(payload["credit_wallet_id"]),

            amount=_parse_decimal(payload["amount"]),

            idempotency_key=str(payload["idempotency_key"]),

            memo=payload.get("memo"),

            created_by=payload.get("created_by"),

        )

        if payload.get("auto_process", True):

            inst = RTPEngine.process(inst)

        return jsonify({"status": "success", "instruction": _serialize_instruction(inst)}), 201

    except (KeyError, ValueError, RTPError) as err:

        return jsonify({"status": "error", "message": str(err)}), 400





@banking_bp.get("/api/v1/banking/rtp/health")

@_require_banking_auth

def rtp_health():

    return jsonify({"health": RTPEngine.healthcheck(), "metrics": RTPEngine.metrics()}), 200





# -----------------------------------------------------------------------------

# Customer Wallet Endpoints

# -----------------------------------------------------------------------------

@banking_bp.get("/api/v1/banking/wallets/<int:wallet_id>/balance")

@_require_banking_auth

def get_wallet_balance(wallet_id: int):

    wallet = db.session.get(CustomerWallet, wallet_id)

    if not wallet:

        return jsonify({"status": "error", "message": "Wallet not found."}), 404

    bal = WalletEngine.get_balance(wallet)

    return jsonify({"wallet_id": wallet.id, "balance": str(bal), "status": str(getattr(wallet, "status", ""))}), 200





@banking_bp.post("/api/v1/banking/wallets/<int:wallet_id>/deposit")

@_require_banking_auth

def deposit_wallet(wallet_id: int):

    wallet = db.session.get(CustomerWallet, wallet_id)

    if not wallet:

        return jsonify({"status": "error", "message": "Wallet not found."}), 404

    payload = request.get_json(silent=True) or {}

    try:

        updated = WalletEngine.deposit(

            wallet=wallet,

            amount=_parse_decimal(payload["amount"]),

            reference_id=str(payload["reference_id"]),

            cash_account_id=int(payload["cash_account_id"]),

            wallet_account_id=int(payload["wallet_account_id"]),

            description=payload.get("description"),

        )

        return jsonify({"status": "success", "wallet_id": updated.id, "balance": str(WalletEngine.get_balance(updated))}), 200

    except (KeyError, ValueError, WalletError) as err:

        return jsonify({"status": "error", "message": str(err)}), 400





@banking_bp.post("/api/v1/banking/wallets/<int:wallet_id>/withdraw")

@_require_banking_auth

def withdraw_wallet(wallet_id: int):

    wallet = db.session.get(CustomerWallet, wallet_id)

    if not wallet:

        return jsonify({"status": "error", "message": "Wallet not found."}), 404

    payload = request.get_json(silent=True) or {}

    try:

        updated = WalletEngine.withdraw(

            wallet=wallet,

            amount=_parse_decimal(payload["amount"]),

            reference_id=str(payload["reference_id"]),

            cash_account_id=int(payload["cash_account_id"]),

            wallet_account_id=int(payload["wallet_account_id"]),

            description=payload.get("description"),

        )

        return jsonify({"status": "success", "wallet_id": updated.id, "balance": str(WalletEngine.get_balance(updated))}), 200

    except (KeyError, ValueError, WalletError) as err:

        return jsonify({"status": "error", "message": str(err)}), 400





@banking_bp.post("/api/v1/banking/wallets/transfer")

@_require_banking_auth

def transfer_wallets():

    payload = request.get_json(silent=True) or {}

    try:

        sender = db.session.get(CustomerWallet, int(payload["sender_wallet_id"]))

        receiver = db.session.get(CustomerWallet, int(payload["receiver_wallet_id"]))

        if not sender or not receiver:

            return jsonify({"status": "error", "message": "Sender or receiver wallet not found."}), 404

        result = WalletEngine.transfer(

            sender_wallet=sender,

            receiver_wallet=receiver,

            amount=_parse_decimal(payload["amount"]),

            reference_id=str(payload["reference_id"]),

            description=payload.get("description"),

        )

        return jsonify({"status": "success", "transfer": result}), 200

    except (KeyError, ValueError, WalletError) as err:

        return jsonify({"status": "error", "message": str(err)}), 400





@banking_bp.post("/api/v1/banking/wallets/<int:wallet_id>/freeze")

@_require_banking_auth

def freeze_wallet(wallet_id: int):

    wallet = db.session.get(CustomerWallet, wallet_id)

    if not wallet:

        return jsonify({"status": "error", "message": "Wallet not found."}), 404

    WalletEngine.freeze(wallet)

    return jsonify({"status": "success", "wallet_id": wallet.id, "wallet_status": "frozen"}), 200





@banking_bp.post("/api/v1/banking/wallets/<int:wallet_id>/unfreeze")

@_require_banking_auth

def unfreeze_wallet(wallet_id: int):

    wallet = db.session.get(CustomerWallet, wallet_id)

    if not wallet:

        return jsonify({"status": "error", "message": "Wallet not found."}), 404

    WalletEngine.unfreeze(wallet)

    return jsonify({"status": "success", "wallet_id": wallet.id, "wallet_status": "active"}), 200





# -----------------------------------------------------------------------------

# Reconciliation Endpoint

# -----------------------------------------------------------------------------

@banking_bp.get("/api/v1/banking/reconcile")

@_require_banking_auth

def reconcile_ledger():

    try:

        report = ReconciliationEngine.full_reconciliation_report()

        return jsonify({"status": "success", "report": report}), 200

    except ReconciliationError as err:

        return jsonify({"status": "error", "message": str(err)}), 409





# -----------------------------------------------------------------------------

# Discrepancy Normalization, Processor Audit & Statement Endpoints

# -----------------------------------------------------------------------------

import tempfile

from pathlib import Path as _Path

from flask import Response

from app.services.discrepancy import correct_discrepancies

from app.services.payment_auditor import audit_processor_logs

from app.services.pdf_parser import parse_pdf

from app.services.statement_service import generate_statement_pdf, get_last_statement_data





@banking_bp.post("/api/v1/banking/reconcile/discrepancies")

@_require_banking_auth

def normalize_statement_discrepancies():

    payload = request.get_json(silent=True) or {}

    records = payload.get("statements") or []

    corrected = correct_discrepancies(records)

    return jsonify({"status": "success", "count": len(corrected), "statements": corrected}), 200





@banking_bp.post("/api/v1/banking/audit-processor")

@_require_banking_auth

def audit_payment_processor():

    payload = request.get_json(silent=True) or {}

    processor_name = str(payload.get("processor_name") or "default")

    transactions = payload.get("transactions") or []

    report = audit_processor_logs(processor_name, transactions)

    return jsonify({"status": "success", "audit": report}), 200





@banking_bp.get("/api/v1/banking/statements/<int:user_id>/latest")

@_require_banking_auth

def latest_statement_json(user_id: int):

    data = get_last_statement_data(user_id)

    if not data:

        return jsonify({"status": "error", "message": "No statement found."}), 404

    return jsonify({"status": "success", "statement": data}), 200





@banking_bp.get("/api/v1/banking/statements/<int:user_id>/latest.pdf")

@_require_banking_auth

def latest_statement_pdf(user_id: int):

    pdf_bytes = generate_statement_pdf(user_id)

    return Response(pdf_bytes, mimetype="application/pdf")





@banking_bp.post("/api/v1/banking/statements/parse")

@_require_banking_auth

def parse_uploaded_statement_pdf():

    uploaded = request.files.get("file")

    if not uploaded:

        return jsonify({"status": "error", "message": "Missing PDF file upload."}), 400

    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=True) as tmp:

        uploaded.save(tmp.name)

        parsed = parse_pdf(_Path(tmp.name))

    return jsonify({"status": "success", "records": parsed}), 200

