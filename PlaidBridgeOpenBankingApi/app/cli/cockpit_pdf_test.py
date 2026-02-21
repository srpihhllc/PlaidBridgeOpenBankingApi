# =============================================================================
# FILE: app/cli/cockpit_pdf_test.py
# DESCRIPTION: CLI harness to test the Cockpit PDF test route end-to-end.
# =============================================================================

import json
import sys

import click
import requests
from flask import current_app

from app.telemetry.ttl_emit import trace_log, ttl_emit


@click.command("test-cockpit-pdf")
@click.option("--host", default="http://127.0.0.1:5000", help="Base URL of the Flask app")
@click.option("--path", default="/cockpit/pdf-test", help="Relative path to the test route")
@click.option(
    "--job-id",
    default="cli-test-001",
    help="Optional job ID to include in telemetry meta.",
)
@click.option(
    "--user-id",
    default=0,
    type=int,
    help="Optional user ID to include in telemetry meta (0 for system).",
)
@click.option("--timeout", default=10, type=int, help="Request timeout in seconds.")
@click.option(
    "--no-exit",
    is_flag=True,
    default=False,
    help="Do not call sys.exit() after completion.",
)
@click.option(
    "--verbose",
    is_flag=True,
    default=False,
    help="Echo detailed output to the console.",
)
@click.option(
    "--strict",
    is_flag=True,
    default=False,
    help="Treat warnings as failures (non-zero exit).",
)
def test_cockpit_pdf(host, path, job_id, user_id, timeout, no_exit, verbose, strict):
    """
    CLI command to hit the Cockpit PDF test route and log results.
    """
    url = f"{host.rstrip('/')}{path}"
    if verbose:
        click.echo(f"📡 Hitting Cockpit PDF test route: {url} (Timeout: {timeout}s)")

    ttl_key = "ttl:test:cockpit_pdf"
    ttl_val = 300
    client = current_app.redis_client
    meta_data = {"job_id": job_id, "user_id": user_id}

    exit_code = 1  # default to failure

    try:
        resp = requests.get(url, timeout=timeout)
        status_code = resp.status_code
        content_type = resp.headers.get("Content-Type", "unknown")

        if verbose:
            click.echo(f"🔍 Status: {status_code}")
            click.echo(f"📄 Content-Type: {content_type}")

        trace_details = {
            "status_code": status_code,
            "content_type": content_type,
            "url": url,
            **meta_data,
        }

        if status_code == 200 and "application/pdf" in content_type.lower():
            if verbose:
                click.echo("✅ PDF route responded successfully.")
            exit_code = 0
            ttl_emit(
                key=ttl_key,
                status="success",
                client=client,
                ttl=ttl_val,
                meta=meta_data,
            )
            trace_log(
                "cli/cockpit_pdf_test",
                json.dumps({"message": "PDF route OK", **trace_details}),
            )
        else:
            if verbose:
                click.echo("⚠️ Unexpected response from PDF route.")
            exit_code = 1 if strict else 0
            ttl_emit(
                key=ttl_key,
                status=f"warn:{status_code}",
                client=client,
                ttl=ttl_val,
                meta=meta_data,
            )
            trace_log(
                "cli/cockpit_pdf_test_warn",
                json.dumps({"message": "Unexpected status code", **trace_details}),
            )

    except Exception as e:
        if verbose:
            click.echo(f"❌ Error hitting PDF route: {e}")
        error_type = type(e).__name__
        error_status = f"error:{error_type}"
        ttl_emit(key=ttl_key, status=error_status, client=client, ttl=ttl_val, meta=meta_data)
        error_payload = {
            "message": f"Network/Request error: {str(e)}",
            "error_type": error_type,
            "url": url,
            **meta_data,
        }
        trace_log("cli/cockpit_pdf_test_error", json.dumps(error_payload))
        exit_code = 1

    finally:
        if not no_exit:
            sys.exit(exit_code)
