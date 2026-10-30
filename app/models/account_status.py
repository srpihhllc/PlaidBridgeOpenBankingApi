#/home/srpihhllc/PlaidBridgeOpenBankingApi/app/models/account_status.py

from enum import Enum


class AccountStatus(str, Enum):
    ACTIVE = "active"
    PENDING = "pending"
    FROZEN = "frozen"
    BLOCKED = "blocked"
    CLOSED = "closed"