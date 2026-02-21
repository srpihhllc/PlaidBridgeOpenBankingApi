# app/routes/disputes.py

import hashlib
import logging
import os

from flask import Blueprint, abort, send_file

from app.models.dispute_log import DisputeLog

disputes_bp = Blueprint("disputes", __name__)
logger = logging.getLogger(__name__)


# ---------- TXT Download Endpoint ----------
@disputes_bp.route("/api/download/letter/<int:log_id>", methods=["GET"])
def download_txt(log_id):
    path = f"storage/disputes/{log_id}.txt"
    try:
        if not os.path.exists(path):
            logger.warning(f"TXT not found for DisputeLog {log_id}")
            abort(404)
        logger.info(f"Dispatching TXT: {path}")
        return send_file(path, as_attachment=True)
    except Exception as e:
        logger.error(f"TXT send_file failed for DisputeLog {log_id}: {e}")
        abort(500)


# ---------- PDF Download Endpoint ----------
@disputes_bp.route("/api/download/pdf/<int:log_id>", methods=["GET"])
def download_pdf(log_id):
    path = f"storage/disputes/{log_id}.pdf"
    try:
        if not os.path.exists(path):
            logger.warning(f"PDF not found for DisputeLog {log_id}")
            abort(404)
        logger.info(f"Dispatching PDF: {path}")
        return send_file(path, as_attachment=True)
    except Exception as e:
        logger.error(f"PDF send_file failed for DisputeLog {log_id}: {e}")
        abort(500)


# ---------- ZIP Bundle Endpoint ----------
@disputes_bp.route("/api/download/bundle/<int:log_id>", methods=["GET"])
def download_zip(log_id):
    path = f"storage/bundles/dispute_{log_id}_bundle.zip"
    try:
        if not os.path.exists(path):
            logger.warning(f"ZIP not found for DisputeLog {log_id}")
            abort(404)
        logger.info(f"Dispatching ZIP: {path}")
        return send_file(path, as_attachment=True)
    except Exception as e:
        logger.error(f"ZIP send_file failed for DisputeLog {log_id}: {e}")
        abort(500)


# ---------- Artifact Status Check Endpoint ----------
@disputes_bp.route("/api/disputes/status/<int:log_id>", methods=["GET"])
def dispute_status(log_id):
    log = DisputeLog.query.get_or_404(log_id)
    txt_path = f"storage/disputes/{log_id}.txt"
    pdf_path = f"storage/disputes/{log_id}.pdf"
    zip_path = f"storage/bundles/dispute_{log_id}_bundle.zip"

    hash_verified = False
    if os.path.exists(txt_path):
        try:
            with open(txt_path, "rb") as f:
                content_hash = hashlib.sha256(f.read()).hexdigest()
            hash_verified = content_hash == log.content_hash
        except Exception as e:
            logger.error(f"Hash verification failed for DisputeLog {log_id}: {e}")

    status = {
        "txt": "available" if os.path.exists(txt_path) else "missing",
        "pdf": "available" if os.path.exists(pdf_path) else "missing",
        "zip": "available" if os.path.exists(zip_path) else "missing",
        "hash_verified": hash_verified,
    }

    logger.info(f"Health check for DisputeLog {log_id}: {status}")
    return status
