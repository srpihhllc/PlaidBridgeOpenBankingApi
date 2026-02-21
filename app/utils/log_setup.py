# app/utils/log_setup.py
#
# PythonAnywhere‑safe logging configuration.
# Removes all file handlers (RotatingFileHandler) because PythonAnywhere
# rotates logs externally, which breaks file descriptors and causes:
#   OSError: [Errno 116] Stale file handle
#
# This module now configures stdout‑only logging, which is the correct
# and stable approach for WSGI environments on PythonAnywhere.

import logging


def configure_logging(log_path=None):
    """Configure logging safely for PythonAnywhere (stdout only)."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[logging.StreamHandler()],
    )
