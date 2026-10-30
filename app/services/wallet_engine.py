# =============================================================================
# FILE: app/services/wallet_engine.py
#
# DESCRIPTION:
#     Customer wallet orchestration engine.
#
# PURPOSE:
#     - deposits
#     - withdrawals
#     - internal transfers
#     - wallet lifecycle controls
#
# ACCOUNTING RULE:
#     Every monetary action must generate a
#     balanced ledger entry through LedgerEngine.
#
# SOURCE OF TRUTH:
#     JournalEntry
#
# DESIGN PRINCIPLES:
#     - Defensive validation
#     - Frozen-wallet enforcement
#     - Decimal-safe arithmetic
#     - Double-entry accounting
#     - Clear operational exceptions
#
# =============================================================================

from __future__ import annotations

from decimal import Decimal

from app.extensions import db
from app.models.account_status import AccountStatus
from app.models.customer_wallet import CustomerWallet
from app.services.ledger_engine import LedgerEngine


class WalletError(Exception):
    """Base wallet exception."""


class InsufficientFundsError(WalletError):
    """Raised when wallet balance is insufficient."""


class FrozenWalletError(WalletError):
    """Raised when activity is attempted on a frozen wallet."""


class WalletEngine:
    """
    Customer wallet orchestration engine.

    Responsibilities:
        - Deposits
        - Withdrawals
        - Internal transfers
        - Freeze / unfreeze controls

    Ledger remains the accounting source of truth while
    wallet.balance serves as an operational cached balance.
    """

    # =========================================================================
    # Validation Helpers
    # =========================================================================

    @staticmethod
    def _to_decimal(amount) -> Decimal:
        """
        Convert inbound amount safely to Decimal.
        """
        amount = Decimal(str(amount))

        if amount <= Decimal("0"):
            raise ValueError("Amount must be greater than zero")

        return amount

    @staticmethod
    def _assert_not_frozen(wallet: CustomerWallet) -> None:
        """
        Block monetary activity on frozen wallets.
        """

        if getattr(wallet, "is_frozen", False):
            raise FrozenWalletError("Wallet is frozen")

        if wallet.status == AccountStatus.FROZEN:
            raise FrozenWalletError("Wallet is frozen")

    @staticmethod
    def _wallet_balance(wallet: CustomerWallet) -> Decimal:
        """
        Safely normalize wallet balance.
        """

        if wallet.balance is None:
            return Decimal("0.00")

        return Decimal(str(wallet.balance))

    # =========================================================================
    # Deposits
    # =========================================================================

    @staticmethod
    def deposit(
        *,
        wallet: CustomerWallet,
        amount,
        reference_id: str,
        cash_account_id: int,
        wallet_account_id: int,
        description: str | None = None,
    ) -> CustomerWallet:
        """
        Deposit funds.

        Ledger Impact:

            Debit:
                Cash Asset

            Credit:
                Customer Wallet Liability
        """

        WalletEngine._assert_not_frozen(wallet)

        amount = WalletEngine._to_decimal(amount)

        LedgerEngine.post(
            debit_account_id=cash_account_id,
            credit_account_id=wallet_account_id,
            amount=amount,
            reference_id=reference_id,
            description=description,
        )

        wallet.balance = (
            WalletEngine._wallet_balance(wallet)
            + amount
        )

        db.session.add(wallet)

        return wallet

    # =========================================================================
    # Withdrawals
    # =========================================================================

    @staticmethod
    def withdraw(
        *,
        wallet: CustomerWallet,
        amount,
        reference_id: str,
        cash_account_id: int,
        wallet_account_id: int,
        description: str | None = None,
    ) -> CustomerWallet:
        """
        Withdraw funds.

        Ledger Impact:

            Debit:
                Customer Wallet Liability

            Credit:
                Cash Asset
        """

        WalletEngine._assert_not_frozen(wallet)

        amount = WalletEngine._to_decimal(amount)

        current_balance = WalletEngine._wallet_balance(wallet)

        if current_balance < amount:
            raise InsufficientFundsError(
                "Insufficient funds"
            )

        LedgerEngine.post(
            debit_account_id=wallet_account_id,
            credit_account_id=cash_account_id,
            amount=amount,
            reference_id=reference_id,
            description=description,
        )

        wallet.balance = current_balance - amount

        db.session.add(wallet)

        return wallet

    # =========================================================================
    # Internal Transfers
    # =========================================================================

    @staticmethod
    def transfer(
        *,
        sender_wallet: CustomerWallet,
        receiver_wallet: CustomerWallet,
        amount,
        reference_id: str,
        description: str | None = None,
    ) -> dict:
        """
        Internal wallet-to-wallet transfer.

        No external cash movement occurs.

        Ledgering can be implemented separately if your
        architecture later introduces explicit wallet
        liability sub-ledgers.
        """

        WalletEngine._assert_not_frozen(sender_wallet)
        WalletEngine._assert_not_frozen(receiver_wallet)

        amount = WalletEngine._to_decimal(amount)

        sender_balance = WalletEngine._wallet_balance(
            sender_wallet
        )

        if sender_balance < amount:
            raise InsufficientFundsError(
                "Insufficient funds"
            )

        sender_wallet.balance = (
            sender_balance - amount
        )

        receiver_wallet.balance = (
            WalletEngine._wallet_balance(receiver_wallet)
            + amount
        )

        db.session.add(sender_wallet)
        db.session.add(receiver_wallet)

        return {
            "reference_id": reference_id,
            "amount": str(amount),
            "sender_wallet_id": sender_wallet.id,
            "receiver_wallet_id": receiver_wallet.id,
        }

    # =========================================================================
    # Wallet Controls
    # =========================================================================

    @staticmethod
    def freeze(
        wallet: CustomerWallet,
    ) -> CustomerWallet:
        """
        Freeze wallet activity.
        """

        wallet.is_frozen = True
        wallet.status = AccountStatus.FROZEN

        db.session.add(wallet)

        return wallet

    @staticmethod
    def unfreeze(
        wallet: CustomerWallet,
    ) -> CustomerWallet:
        """
        Restore wallet activity.
        """

        wallet.is_frozen = False
        wallet.status = AccountStatus.ACTIVE

        db.session.add(wallet)

        return wallet

    # =========================================================================
    # Read Helpers
    # =========================================================================

    @staticmethod
    def get_balance(
        wallet: CustomerWallet,
    ) -> Decimal:
        """
        Return normalized wallet balance.
        """

        return WalletEngine._wallet_balance(wallet)