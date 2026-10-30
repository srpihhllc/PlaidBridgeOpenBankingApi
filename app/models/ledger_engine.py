#/home/srpihhllc/PlaidBridgeOpenBankingApi/app/models/ledger_engine.py


from __future__ import annotations

from collections import defaultdict
from decimal import Decimal

from app.models.journal_entry import JournalEntry


class LedgerEngine:

    def __init__(self):

        self._entries: list[JournalEntry] = []

    @property
    def entries(self):

        return self._entries

    def post_entry(
        self,
        debit_account: str,
        credit_account: str,
        amount,
        currency: str = "USD",
        reference_id: str | None = None,
    ) -> JournalEntry:

        entry = JournalEntry(
            debit_account=debit_account,
            credit_account=credit_account,
            amount=amount,
            currency=currency,
            reference_id=reference_id,
        )

        self._entries.append(entry)

        return entry

    def account_balance(
        self,
        account: str,
    ) -> Decimal:

        balance = Decimal("0.00")

        for entry in self._entries:

            if entry.debit_account == account:
                balance += entry.amount

            if entry.credit_account == account:
                balance -= entry.amount

        return balance

    def trial_balance(self):

        balances = defaultdict(
            lambda: Decimal("0.00")
        )

        for entry in self._entries:

            balances[
                entry.debit_account
            ] += entry.amount

            balances[
                entry.credit_account
            ] -= entry.amount

        return dict(balances)

    def is_balanced(self) -> bool:

        debit_total = sum(
            e.amount
            for e in self._entries
        )

        credit_total = sum(
            e.amount
            for e in self._entries
        )

        return debit_total == credit_total