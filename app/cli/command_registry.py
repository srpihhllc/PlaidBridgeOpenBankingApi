# /home/srpihhllc/PlaidBridgeOpenBankingApi/app/cli/command_registry.py

from cockpit_core import register_command  # or wherever your central registry lives
from tiles.boot_probe_blueprint_reg import probe_blueprint_reg
from tiles.boot_probe_env_vars import probe_env_vars
from tiles.boot_probe_redis_ping import probe_redis_ping

register_command("probe-redis-ping", probe_redis_ping)
register_command("probe-env-vars", probe_env_vars)
register_command("probe-blueprint-reg", probe_blueprint_reg)

"""
Cockpit Command Registry

Maps command names to their callable paths for use in CLI inspector overlays,
remote invocation tiles, and trace emitters.
"""

COMMANDS = {
    "simulate_form_submission": "cli.simulate_form_submission:run",
    "route_map_dump": "cli.commands:route_map_dump",
    # Add more commands as needed below
    # "grant_pulse": "cli.grant_pulse:run_grant_probe",
    # "redis_inspect": "cli.redis_inspect:run_redis_probe",
}
