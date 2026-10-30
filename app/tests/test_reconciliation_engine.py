from app.services.reconciliation_engine import (
    ReconciliationEngine,
)


def test_full_report_exists():

    report = (
        ReconciliationEngine
        .full_reconciliation_report()
    )

    assert isinstance(report, dict)

    assert (
        "overall_balanced"
        in report
    )


def test_journal_report_exists():

    report = (
        ReconciliationEngine
        .reconcile_journal()
    )

    assert isinstance(report, dict)

    assert "balanced" in report


def test_reserve_position_report_exists():

    report = (
        ReconciliationEngine
        .reconcile_reserve_position()
    )

    assert isinstance(report, dict)

    assert "balanced" in report


def test_assert_balanced_method_exists():

    assert hasattr(
        ReconciliationEngine,
        "assert_balanced",
    )