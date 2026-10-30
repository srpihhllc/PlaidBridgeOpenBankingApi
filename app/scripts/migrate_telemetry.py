#!/usr/bin/env python3
from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path
from typing import Callable, Pattern

ROOT = Path(__file__).resolve().parents[1]
SRC_DIRS = [
    ROOT / "app" / "blueprints",
    ROOT / "app" / "routes",
    ROOT / "app" / "api",
    ROOT / "app",  # Fallback for any stray modules.
]

Replacement = str | Callable[[re.Match[str]], str]

# Legacy imports and shims -> new API.
IMPORT_REWRITES: list[tuple[Pattern[str], str]] = [
    (
        re.compile(r"from\s+app\.utils\.telemetry\s+import\s+log_route_usage\b"),
        "from app.utils.telemetry import inc_metric",
    ),
    (
        re.compile(r"from\s+app\.utils\.telemetry\s+import\s+time_route_latency\b"),
        "from app.utils.telemetry import time_metric",
    ),
    (
        re.compile(r"from\s+app\.utils\.telemetry\s+import\s+increment_counter\b"),
        "from app.utils.telemetry import inc_metric",
    ),
    (
        re.compile(r"from\s+app\.utils\.telemetry\s+import\s+increment_timing\b"),
        "from app.utils.telemetry import time_metric",
    ),
]


def _rewrite_log_route_usage_literal(match: re.Match[str]) -> str:
    endpoint = match.group(3)
    method = match.group(2)
    return (
        "inc_metric('http_requests_total', "
        f"labels={{'method': {method!r}, 'endpoint': {endpoint}}})"
    )


def _rewrite_log_route_usage_vars(match: re.Match[str]) -> str:
    return (
        "inc_metric('http_requests_total', "
        f"labels={{'method': {match.group(1).strip()}, "
        f"'endpoint': {match.group(2).strip()}}})"
    )


def _rewrite_time_route_latency_literal(match: re.Match[str]) -> str:
    endpoint = match.group(3)
    method = match.group(2)
    return (
        "@time_metric('http_request_duration_seconds', "
        f"labels={{'method': {method!r}, 'endpoint': {endpoint}}})"
    )


def _rewrite_time_route_latency_vars(match: re.Match[str]) -> str:
    return (
        "@time_metric('http_request_duration_seconds', "
        f"labels={{'method': {match.group(1).strip()}, "
        f"'endpoint': {match.group(2).strip()}}})"
    )


CALL_REWRITES: list[tuple[Pattern[str], Replacement]] = [
    # log_route_usage("METHOD", "/endpoint")
    (
        re.compile(
            r"\blog_route_usage\(\s*(['\"])(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)\1"
            r"\s*,\s*(['\"])(.+?)\3\s*\)"
        ),
        _rewrite_log_route_usage_literal,
    ),
    # log_route_usage(method_var, endpoint_var)
    (
        re.compile(r"\blog_route_usage\(\s*([^,)]+)\s*,\s*([^)]+)\)"),
        _rewrite_log_route_usage_vars,
    ),
    # time_route_latency("METHOD", "/endpoint")
    (
        re.compile(
            r"@time_route_latency\(\s*(['\"])(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS)\1"
            r"\s*,\s*(['\"])(.+?)\3\s*\)"
        ),
        _rewrite_time_route_latency_literal,
    ),
    # time_route_latency(method_var, endpoint_var)
    (
        re.compile(r"@time_route_latency\(\s*([^,)]+)\s*,\s*([^)]+)\)"),
        _rewrite_time_route_latency_vars,
    ),
    # increment_counter(name) -> inc_metric(name)
    (
        re.compile(r"\bincrement_counter\(\s*([^)]+)\)"),
        lambda match: f"inc_metric({match.group(1).strip()})",
    ),
    # increment_timing('metric') -> @time_metric('metric')
    (
        re.compile(r"@increment_timing\(\s*([^)]]*)\)"),
        lambda match: f"@time_metric({match.group(1).strip()})",
    ),
]

# Set a pattern and replacement here if a DB logging migration is needed.
DB_LOG_REWRITE: Pattern[str] | None = None
DB_LOG_REPLACEMENT = "db_log_event"


def process_file(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    original = text

    for pattern, import_replacement in IMPORT_REWRITES:
        text = pattern.sub(import_replacement, text)

    for pattern, call_replacement in CALL_REWRITES:
        text = pattern.sub(call_replacement, text)

    if DB_LOG_REWRITE is not None:
        text = DB_LOG_REWRITE.sub(DB_LOG_REPLACEMENT, text)

    if text == original:
        return False

    backup = path.with_suffix(path.suffix + ".bak")
    shutil.copy2(path, backup)
    path.write_text(text, encoding="utf-8")
    return True


def main() -> None:
    changed: list[str] = []
    scanned = 0

    for base in SRC_DIRS:
        if not base.exists():
            continue

        for path in base.rglob("*.py"):
            scanned += 1
            try:
                if process_file(path):
                    changed.append(str(path.relative_to(ROOT)))
            except Exception as exc:
                print(f"[ERROR] Failed processing {path}: {exc}", file=sys.stderr)

    print(f"Scanned {scanned} files.")
    if changed:
        print("Changed files:")
        for changed_path in changed:
            print(f" - {changed_path}")
        print("\nBackups (.bak) created alongside each modified file.")
        print(
            "Next: run tests, then remove shims from app/utils/telemetry.py "
            "once imports are clean."
        )
    else:
        print("No changes needed. Blueprint code already using new telemetry API.")


if __name__ == "__main__":
    main()