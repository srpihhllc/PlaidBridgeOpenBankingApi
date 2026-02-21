# app/dto/category_summary_dto.py

from dataclasses import dataclass


@dataclass
class CategorySummaryDTO:
    total_amount: float
    income: float
    expenses: float
    net_cash_flow: float
    categories: dict[str, float]
