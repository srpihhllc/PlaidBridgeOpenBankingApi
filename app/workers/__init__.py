# app/workers/__init__.py
"""
Worker package for PlaidBridgeOpenBankingApi.

Exports the sync_worker module cleanly so that static analyzers
can resolve the symbol, and downstream imports receive the actual module.
"""

from . import sync_worker

__all__ = ["sync_worker"]
