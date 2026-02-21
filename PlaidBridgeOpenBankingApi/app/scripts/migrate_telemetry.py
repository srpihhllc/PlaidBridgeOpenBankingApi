# /home/srpihhllc/PlaidBridgeOpenBankingApi/app/scripts/migrate_telemetry.py

#!/usr/bin/env python3
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC_DIRS = [
    ROOT / "app" / "blueprints",
    ROOT / "app" / "routes",
    ROOT / "app" / "api",
    ROOT / "app",  # fallback for any stray modules
]

# Patterns: legacy imports and shims -> new API
IMPORT_REWRITES = [
    # log_route_usage -> inc_metric
    (
        re.compile(r"from\s+app\.utils\.telemetry\s+import\s+log_route_usage\b"),
        "from app.utils.telemetry import inc_metric",
    ),
    # time_route_latency -> time_metric
    (
        re.compile(r"from\s+app\.utils\.telemetry\s+import\s+time_route_latency\b"),
        "from app.utils.telemetry import time_metric",
    ),
    # increment_counter -> inc_metric (if used)
    (
        re.compile(r"from\s+app\.utils\.telemetry\s+import\s+increment_counter\b"),
        "from app.utils.telemetry import inc_metric",
    ),
    # increment_timing -> time_metric (decorator)
    (
        re.compile(r"from\s+app\.utils\.telemetry\s+import\s+increment_timing\b"),
        "from app.utils.telemetry import time_metric",
    ),
    # log_identity_event import stays, but ensure present if needed
]


def _rewrite_log_route_usage_literal(match: re.Match) -> str:
    endpoint = match.group(0).split(",")[1].strip()
    return (
        "inc_metric('http_requests_total', "
        f"labels={{'method': {match.group(2)!r}, 'endpoint': {endpoint}}})"
    )


def _rewrite_log_route_usage_vars(match: re.Match) -> str:
    return (
        "inc_metric('http_requests_total', "
        f"labels={{'method': {match.group(1).strip()}, "
        f"'endpoint': {match.group(2).strip()}}})"
    )


def _rewrite_time_route_latency_literal(match: re.Match) -> str:
    endpoint = match.group(0).split(",")[1].strip()
    return (
        "@time_metric('http_request_duration_seconds', "
        f"labels={{'method': {match.group(2)!r}, 'endpoint': {endpoint}}})"
    )


def _rewrite_time_route_latency_vars(match: re.Match) -> str:
    return (
        "@time_metric('http_request_duration_seconds', "
        f"labels={{'method': {match.group(1).strip()}, "
        f"'endpoint': {match.group(2).strip()}}})"
    )


CALL_REWRITES = [
    # log_route_usage("METHOD", "/endpoint")
    (
        re.compile(
            r"\blog_route_usage\(\s*(['\"])(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)\1\s*,\s*(['\"]).+?\3\s*\)"
        ),
        _rewrite_log_route_usage_literal,
    ),
    # inc_metric for generic: log_route_usage(method_var, endpoint_var)
    (
        re.compile(r"\blog_route_usage\(\s*([^\),]+)\s*,\s*([^\)]+)\)"),
        _rewrite_log_route_usage_vars,
    ),
    # time_route_latency("METHOD", "/endpoint") decorator
    (
        re.compile(
            r"@time_route_latency\(\s*(['\"])(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)\1\s*,\s*(['\"]).+?\3\s*\)"
        ),
        _rewrite_time_route_latency_literal,
    ),
    # time_route_latency(method_var, endpoint_var)
    (
        re.compile(r"@time_route_latency\(\s*([^\),]+)\s*,\s*([^\)]+)\)"),
        _rewrite_time_route_latency_vars,
    ),
    # increment_counter(name) -> inc_metric(name)
    (
        re.compile(r"\bincrement_counter\(\s*([^\)]+)\)"),
        lambda m: f"inc_metric({m.group(1).strip()})",
    ),
    # increment_timing('metric') decorator -> @time_metric('metric')
    (
        re.compile(r"@increment_timing\(\s*([^\)]*)\)"),
        lambda m: f"@time_metric({m.group(1).strip()})",
    ),
]

# Optional: deprecate direct DB logging in favor of db_log_event if you have it exposed
DB_LOG_REWRITE = None  # supply a regex if needed


def process_file(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    original = text

    # Imports
    for pattern, replacement in IMPORT_REWRITES:
        text = pattern.sub(replacement, text)

    # Calls/decorators
    for pattern, replacement in CALL_REWRITES:
        text = pattern.sub(replacement if isinstance(replacement, str) else replacement, text)

    if DB_LOG_REWRITE:
        text = DB_LOG_REWRITE.sub(..., text)  # customize if you need DB migration

    if text != original:
        backup = path.with_suffix(path.suffix + ".bak")
        shutil.copy2(path, backup)
        path.write_text(text, encoding="utf-8")
        return True
    return False


def main():
    changed = []
    scanned = 0
    for base in SRC_DIRS:
        if not base.exists():
            continue
        for path in base.rglob("*.py"):
            scanned += 1
            try:
                if process_file(path):
                    changed.append(str(path.relative_to(ROOT)))
            except Exception as e:
                print(f"[ERROR] Failed processing {path}: {e}", file=sys.stderr)

    print(f"Scanned {scanned} files.")
    if changed:
        print("Changed files:")
        for c in changed:
            print(f" - {c}")
        print("\nBackups (.bak) created alongside each modified file.")
        print(
            "Next: run tests, then remove shims from app/utils/telemetry.py once imports are clean."
        )
    else:
        print("No changes needed. Blueprint code already using new telemetry API.")


if __name__ == "__main__":
    main()
