# app/services/category_analytics.py


from app.dto.category_summary_dto import CategorySummaryDTO
from app.dto.transaction_dto import TransactionDTO


def compute_category_summary(transactions: list[TransactionDTO]) -> CategorySummaryDTO:
    categories: dict[str, float] = {}
    income = 0.0
    expenses = 0.0

    for txn in transactions:
        amt = float(txn.amount)
        cat = txn.category or "Uncategorized"

        categories[cat] = categories.get(cat, 0.0) + amt

        if amt >= 0:
            income += amt
        else:
            expenses += amt

    total = income + expenses
    net = income + expenses

    return CategorySummaryDTO(
        total_amount=total,
        income=income,
        expenses=abs(expenses),
        net_cash_flow=net,
        categories=categories,
    )
