# /home/srpihhllc/PlaidBridgeOpenBankingApi/patch_cache_health.py

import json
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent


LEGACY_ENDPOINTS = {
    "admin.cache_health",
    "admin_ui.cache_health",
}


def patch_sidebar():
    sidebar_path = (
        BASE_DIR
        / "app"
        / "templates"
        / "admin"
        / "admin_sidebar.html"
    )

    if not sidebar_path.exists():
        print(f"File not found: {sidebar_path}")
        return

    content = sidebar_path.read_text(encoding="utf-8")

    updated_content = (
        content
        .replace(
            "url_for('admin.cache_health')",
            "url_for('diagnostics.cache_health')",
        )
        .replace(
            "url_for('admin_ui.cache_health')",
            "url_for('diagnostics.cache_health')",
        )
        .replace(
            "request.endpoint == 'admin.cache_health'",
            "request.endpoint == 'diagnostics.cache_health'",
        )
        .replace(
            "request.endpoint == 'admin_ui.cache_health'",
            "request.endpoint == 'diagnostics.cache_health'",
        )
    )

    if content == updated_content:
        print(f"No sidebar updates needed: {sidebar_path}")
        return

    sidebar_path.write_text(updated_content, encoding="utf-8")
    print(f"Updated sidebar: {sidebar_path}")


def update_expected_endpoints():
    endpoints_path = BASE_DIR / "expected_endpoints.json"

    if not endpoints_path.exists():
        print(f"File not found: {endpoints_path}")
        return

    with endpoints_path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    if not isinstance(data, list):
        print(
            "Skipped expected_endpoints.json: "
            "expected a JSON list"
        )
        return

    updated_data = [
        endpoint
        for endpoint in data
        if endpoint not in LEGACY_ENDPOINTS
    ]

    if updated_data == data:
        print(
            "No legacy endpoints found in "
            f"{endpoints_path}"
        )
        return

    with endpoints_path.open("w", encoding="utf-8") as file:
        json.dump(updated_data, file, indent=2)
        file.write("\n")

    print(f"Removed legacy endpoints from: {endpoints_path}")


def update_route_snapshot():
    snapshot_path = (
        BASE_DIR
        / "app"
        / "tests"
        / "route_snapshot.json"
    )

    if not snapshot_path.exists():
        print(f"File not found: {snapshot_path}")
        return

    with snapshot_path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    modified = False

    if isinstance(data, dict):
        for endpoint in LEGACY_ENDPOINTS:
            if endpoint in data:
                del data[endpoint]
                modified = True

    elif isinstance(data, list):
        original_data = data

        data = [
            item
            for item in data
            if not (
                isinstance(item, str)
                and item in LEGACY_ENDPOINTS
            )
            and not (
                isinstance(item, dict)
                and item.get("endpoint") in LEGACY_ENDPOINTS
            )
        ]

        modified = data != original_data

    else:
        print(
            "Skipped route snapshot: "
            "expected a JSON object or list"
        )
        return

    if not modified:
        print(
            "No legacy route entries found in: "
            f"{snapshot_path}"
        )
        return

    with snapshot_path.open("w", encoding="utf-8") as file:
        json.dump(data, file, indent=2)
        file.write("\n")

    print(f"Removed legacy routes from: {snapshot_path}")


def main():
    patch_sidebar()
    update_expected_endpoints()
    update_route_snapshot()


if __name__ == "__main__":
    main()