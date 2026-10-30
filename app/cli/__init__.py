#/home/srpihhllc/PlaidBridgeOpenBankingApi/app/cli/__init__.py
"""
Cockpit CLI Command Registry

This module registers all cockpit-grade CLI commands for operator access.

Rules:
- Only import Click.Command objects decorated with @click.command.
- No CLI logic belongs here; this module only registers commands.
- Use ``flask_app`` as the parameter name in ``init_app()``.
- Keep ``cli_command_lattice`` updated when adding or removing commands.
"""

from flask import Flask

# ---------------------------------------------------------------------------
# Basic compatibility commands
# ---------------------------------------------------------------------------
from app.cli_commands.basic_commands import init_db, verify_sandbox

# ---------------------------------------------------------------------------
# Template drift and inheritance audits
# ---------------------------------------------------------------------------
from app.cli_commands.cli_template_audit import template_audit
from app.cli_commands.cli_template_block_audit import (
    template_block_audit_command,
)
from app.cli_commands.cli_template_inheritance import (
    template_inheritance_command,
)

# ---------------------------------------------------------------------------
# Diagnostics and core commands
# ---------------------------------------------------------------------------
from app.cli_commands.diagnostics_cli import diagnostics_full
from app.cli_commands.emit_blueprint_inspector import emit_blueprint_inspector
from app.cli_commands.route_map_dump import route_map_command as route_map_dump
from app.cli_commands.sweep_endpoints import sweep_endpoints
from app.cli_commands.validate_relationships import (
    validate_relationships_command,
)
from app.cli_commands.blueprint_emit import blueprint_emit

# Endpoint tracer; this is separate from the template drift audit.
from app.scripts.cli_template_tracer import trace_templates_command

# ---------------------------------------------------------------------------
# Cockpit commands
# ---------------------------------------------------------------------------
from .cockpit_pdf_test import test_cockpit_pdf
from .doctor import doctor
from .grant_pulse import grant_pulse
from .reset_and_reseed import reset_and_reseed

# ---------------------------------------------------------------------------
# Seeder commands
# ---------------------------------------------------------------------------
from .seed_admin import seed_admin
from .seed_all import seed_all
from .seed_everything import seed_everything
from .seed_fraud_cases import seed_fraud_cases
from .seed_lender import seed_lender
from .seed_mock_bank_transfers_all import seed_mock_bank_transfers_all
from .seed_mock_bank_transfers_audit import seed_mock_bank_transfers_audit
from .seed_mock_bank_transfers_flags import seed_mock_bank_transfers_flags
from .seed_mock_bank_transfers_summary import seed_mock_bank_transfers_summary
from .seed_mock_transactions import seed_mock_transactions
from .seed_subscriber import seed_subscriber
from .seed_timeline import seed_timeline
from .seed_todos import seed_todos
from .statement_leaders import statement_leaders
from .statement_pulse import statement_pulse


# =============================================================================
# CLI Registration
# =============================================================================


def init_app(flask_app: Flask) -> None:
    """
    Attach all cockpit commands directly to Flask's built-in CLI.
    """

    # Basic compatibility commands
    flask_app.cli.add_command(verify_sandbox)
    flask_app.cli.add_command(init_db)

    # Core commands
    flask_app.cli.add_command(route_map_dump)
    flask_app.cli.add_command(validate_relationships_command)
    flask_app.cli.add_command(template_inheritance_command)
    flask_app.cli.add_command(template_block_audit_command)
    flask_app.cli.add_command(sweep_endpoints)

    # Pulses and diagnostics
    flask_app.cli.add_command(grant_pulse)
    flask_app.cli.add_command(statement_pulse)
    flask_app.cli.add_command(statement_leaders)
    flask_app.cli.add_command(emit_blueprint_inspector)
    flask_app.cli.add_command(blueprint_emit)
    flask_app.cli.add_command(test_cockpit_pdf)
    flask_app.cli.add_command(diagnostics_full)

    # Template wiring audit
    flask_app.cli.add_command(trace_templates_command)

    # Template drift audit
    flask_app.cli.add_command(template_audit)

    # Seeder commands
    flask_app.cli.add_command(seed_admin)
    flask_app.cli.add_command(seed_subscriber)
    flask_app.cli.add_command(seed_lender)
    flask_app.cli.add_command(seed_all)
    flask_app.cli.add_command(reset_and_reseed)
    flask_app.cli.add_command(doctor)

    # Cockpit mock-data seeders
    flask_app.cli.add_command(seed_mock_transactions)
    flask_app.cli.add_command(seed_fraud_cases)
    flask_app.cli.add_command(seed_timeline)
    flask_app.cli.add_command(seed_todos)
    flask_app.cli.add_command(seed_everything)

    # Mock-bank-transfer seeders
    flask_app.cli.add_command(seed_mock_bank_transfers_flags)
    flask_app.cli.add_command(seed_mock_bank_transfers_all)
    flask_app.cli.add_command(seed_mock_bank_transfers_summary)
    flask_app.cli.add_command(seed_mock_bank_transfers_audit)


# =============================================================================
# Programmatic command introspection lattice
# =============================================================================

cli_command_lattice = {
    # Basic compatibility commands
    "verify_sandbox": verify_sandbox,
    "init_db": init_db,

    # Core commands
    "route_map_dump": route_map_dump,
    "validate_relationships": validate_relationships_command,
    "template_inheritance": template_inheritance_command,
    "template_block_audit": template_block_audit_command,
    "sweep_endpoints": sweep_endpoints,

    # Pulses and diagnostics
    "grant_pulse": grant_pulse,
    "statement_pulse": statement_pulse,
    "statement_leaders": statement_leaders,
    "emit_blueprint_inspector": emit_blueprint_inspector,
    "blueprint_emit": blueprint_emit,
    "test_cockpit_pdf": test_cockpit_pdf,
    "diagnostics_full": diagnostics_full,

    # Template audits
    "trace_templates": trace_templates_command,
    "template_audit": template_audit,

    # Seeder commands
    "seed_admin": seed_admin,
    "seed_subscriber": seed_subscriber,
    "seed_lender": seed_lender,
    "seed_all": seed_all,
    "reset_and_reseed": reset_and_reseed,
    "doctor": doctor,

    # Cockpit mock-data seeders
    "seed_mock_transactions": seed_mock_transactions,
    "seed_fraud_cases": seed_fraud_cases,
    "seed_timeline": seed_timeline,
    "seed_todos": seed_todos,
    "seed_everything": seed_everything,

    # Mock-bank-transfer seeders
    "seed_mock_bank_transfers_flags": seed_mock_bank_transfers_flags,
    "seed_mock_bank_transfers_all": seed_mock_bank_transfers_all,
    "seed_mock_bank_transfers_summary": seed_mock_bank_transfers_summary,
    "seed_mock_bank_transfers_audit": seed_mock_bank_transfers_audit,
}


# Backward-compatible alias used by existing application code and tests.
register_cli_commands = init_app


__all__ = [
    "init_app",
    "register_cli_commands",
    "cli_command_lattice",
]