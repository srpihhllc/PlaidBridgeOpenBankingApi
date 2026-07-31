import click
from flask.cli import with_appcontext

@click.command("email-telemetry-now")
@with_appcontext
def email_telemetry_now_command():
    """Manually triggers the background telemetry email generation and dispatch sequence."""
    click.echo("🚀 Forcing manual initialization of the reporting subsystem payload...")
    
    # Deferred import to ensure app context is fully loaded before execution
    from app.services.reporting_subsystem import execute_scheduled_report_dispatch
    
    execute_scheduled_report_dispatch()
    click.echo("✨ Sequence complete. Check backend system logs or mailbox for delivery tokens.")