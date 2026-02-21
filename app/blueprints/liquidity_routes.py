# =============================================================================
# FILE: app/blueprints/liquidity_routes.py
# DESCRIPTION: Liquidity dashboard blueprint. Aggregates vault balances and
#              renders cockpit metrics for operator dashboards.
# =============================================================================

from flask import Blueprint, render_template

# 🛠 Fixed import path — BankAccount is defined in app/models/bank_account.py
from app.models.bank_account import BankAccount

liquidity_bp = Blueprint("liquidity_bp", __name__, url_prefix="/dashboard")


@liquidity_bp.route("/liquidity")
def liquidity_dashboard():
    """
    Render the liquidity dashboard.
    - Aggregates balances across all vault accounts
    - Computes dormant account percentage
    - Provides example velocity data for cockpit visualization
    """
    vaults = BankAccount.query.all()
    total_assets = sum(acct.balance for acct in vaults)
    vault_count = len(vaults)
    dormant_count = sum(1 for acct in vaults if acct.balance < 1)
    dormant_pct = round((dormant_count / vault_count) * 100, 2) if vault_count else 0

    # 🧠 Example velocity data — wire Redis or telemetry later
    net_deposits_week = 24872.00
    flow_labels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    flow_values = [3200, 4100, 2800, 3900, 4700, 2100, 4172]

    return render_template(
        "dashboard_liquidity.html",
        total_assets=total_assets,
        vault_count=vault_count,
        dormant_count=dormant_count,
        dormant_pct=dormant_pct,
        net_deposits_week=net_deposits_week,
        flow_labels=flow_labels,
        flow_values=flow_values,
    )
