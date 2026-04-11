#!/usr/bin/env python3
"""
Diagnostic runner for the emit_blueprint_inspector CLI that ensures the
repository root is on sys.path so `import app...` works when run from anywhere.

Usage:
    python diagnostics/run_emit_cli.py
"""
from __future__ import annotations

import pathlib
import sys
import traceback
from click.testing import CliRunner

# Ensure repo root is first on sys.path so `import app...` resolves
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.cli_commands.emit_blueprint_inspector import emit_blueprint_inspector  # noqa: E402


def main() -> None:
    runner = CliRunner()
    res = runner.invoke(emit_blueprint_inspector)

    print("EXIT CODE:", res.exit_code)
    print("OUTPUT:")
    print(res.output)
    print("EXCEPTION:", repr(res.exception))
    if res.exception:
        traceback.print_exception(type(res.exception), res.exception, res.exception.__traceback__, file=sys.stdout)


if __name__ == "__main__":
    main()