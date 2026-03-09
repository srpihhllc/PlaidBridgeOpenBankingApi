# =============================================================================
# FILE: app/constants/__init__.py
# DESCRIPTION: Centralized constants for ignition, telemetry, and session flags.
#              Keeps all magic strings in one place to avoid drift across
#              blueprints and ensures cockpit-grade operator clarity.
# =============================================================================

# ---------------------------------------------------------------------------
# Operator / Ignition
# ---------------------------------------------------------------------------
# Session key used to mark operator mode as active
OPERATOR_MODE_KEY: str = "operator_mode"

# Canonical ignition route for enabling operator mode
IGNITION_ROUTE: str = "/admin/ignite-cortex"

# ---------------------------------------------------------------------------
# Telemetry Key Prefixes
# ---------------------------------------------------------------------------
TRACE_PREFIX: str = "trace"
BOOT_PREFIX: str = "boot"
LOGIN_PREFIX: str = "login"
LOGOUT_PREFIX: str = "logout"

# Blueprint audit trace key
BLUEPRINT_AUDIT_KEY: str = "ttl:cockpit:blueprint_audit_info"

# ---------------------------------------------------------------------------
# TTL Defaults (seconds)
# ---------------------------------------------------------------------------
DEFAULT_TTL: int = 300  # 5 minutes

# ---------------------------------------------------------------------------
# Redis Key Patterns
# ---------------------------------------------------------------------------
# Keys that are considered temporary and safe to purge during sweeps
PURGEABLE_KEY_PREFIXES: tuple[str, ...] = (
    "mfa_code",
    "rate_limit",
    "session",
    f"{TRACE_PREFIX}:",
)

# ---------------------------------------------------------------------------
# Roles
# ---------------------------------------------------------------------------
# Canonical role names used in @roles_required decorators
ROLE_ADMIN: str = "admin"
ROLE_SUPER_ADMIN: str = "super_admin"
ROLE_FINANCE_ADMIN: str = "finance_admin"
ROLE_CREDIT_ADMIN: str = "credit_admin"
ROLE_FRAUD_ADMIN: str = "fraud_admin"
ROLE_TRADELINE_ADMIN: str = "tradeline_admin"

# ---------------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------------
# Used for cockpit dashboards and operator summaries
APP_METADATA_KEYS: tuple[str, ...] = (
    "app",
    "version",
    "env",
    "debug",
    "testing",
    "timezone",
    "db_uri",
    "redis_uri",
    "plaid_env",
    "log_level",
)
