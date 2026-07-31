# =============================================================================
# FILE: app/cli/command_registry.py
# DESCRIPTION: Cockpit Command Registry mapping overlay execution lines.
# =============================================================================

"""
Cockpit Command Registry

Maps command names to their callable paths for use in CLI inspector overlays,
remote invocation tiles, and trace emitters.
"""

try:
    from cockpit_core import register_command
except ImportError:
    # Robust telemetry fallback when execution layer runs independently
    def register_command(name, callable_obj):
        pass

# Guarded discovery loop for core diagnostic tiles
try:
    from tiles.boot_probe_blueprint_reg import probe_blueprint_reg
    from tiles.boot_probe_env_vars import probe_env_vars
    from tiles.boot_probe_redis_ping import probe_redis_ping

    register_command("probe-redis-ping", probe_redis_ping)
    register_command("probe-env-vars", probe_env_vars)
    register_command("probe-blueprint-reg", probe_blueprint_reg)
except ImportError:
    pass

COMMANDS = {
    "simulate_form_submission": "cli.simulate_form_submission:simulate_form_submission_command",
    "route_map_dump": "cli_commands.route_map_dump:route_map_command",
}