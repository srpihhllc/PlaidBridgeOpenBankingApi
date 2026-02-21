# =============================================================================
# FILE: app/utils/log_parser.py
# DESCRIPTION: Parse log lines and scan Redis for trace keys.
# =============================================================================

import re
import sys
from pathlib import Path

sys.path.append("app/utils")
from app.utils.redis_utils import get_redis_client

client = get_redis_client()


def parse_log_line(line: str) -> dict[str, str] | None:
    """
    Parses a single log line to extract timestamp, level, trace_type, and detail.
    Example input:
    [2025-07-31 17:28:09] [INFO] trace:Startup:Boot sequence initialized
    """

    # Bulletproof regex: verbose mode, no fragile escapes, cannot break on paste
    pattern = re.compile(
        r"""
            ^

\[
                (?P<timestamp>.*?)
            \]

\s+

\[
                (?P<level>.*?)
            \]

\s+trace:
                (?P<trace_type>.*?):
                (?P<detail>.*)
            $
        """,
        re.VERBOSE,
    )

    match = pattern.match(line)
    if match:
        return {
            "timestamp": match.group("timestamp").strip(),
            "level": match.group("level").strip(),
            "trace_type": match.group("trace_type").strip(),
            "detail": match.group("detail").strip(),
        }

    return None


def scan_trace_keys(pattern: str = "trace:*") -> list[str]:
    if client is None:
        return []

    keys = client.scan_iter(pattern)
    return [key.decode() if isinstance(key, bytes) else key for key in keys]


def get_ranked_trace_keys(pattern: str = "trace:*", rank: bool = True) -> list[str]:
    if client is None:
        return []

    keys = scan_trace_keys(pattern)

    ranked = sorted(
        keys,
        key=lambda k: client.ttl(k) if rank else 0,
        reverse=True,
    )
    return ranked


def cli_mode(log_path: str) -> None:
    path = Path(log_path)
    if not path.exists():
        print(f"❌ File not found: {log_path}")
        sys.exit(1)

    with path.open("r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            parsed = parse_log_line(line)
            if parsed:
                print(
                    f"[{parsed['timestamp']}] [{parsed['level']}] "
                    f"{parsed['trace_type']} -> {parsed['detail']}"
                )


if __name__ == "__main__":
    if len(sys.argv) == 2:
        cli_mode(sys.argv[1])
    else:
        if client is None:
            print("❌ No Redis client available.")
            sys.exit(1)

        keys = get_ranked_trace_keys("trace:*")
        for key in keys:
            ttl = client.ttl(key)
            print(f"{key} -> TTL: {ttl}s")
