# app/models/admin/cockpit/module_health.py

from importlib import import_module


def check_model(name: str) -> dict:
    """Attempt to import model by name and return health status."""
    result = {
        "model": name,
        "import_path": f"app.models.{name}",
        "exists": False,
        "error": None,
    }
    try:
        mod = import_module(f"app.models.{name}")
        if hasattr(mod, name):
            result["exists"] = True
        else:
            result["error"] = f"'{name}' not found in module"
    except Exception as e:
        result["error"] = str(e)
    return result


def model_import_health():
    """Return health check for key models used in cockpit diagnostics."""
    targets = ["SchemaEvent", "CreditLedger", "PaymentLog", "DisputeLog", "User"]
    results = []
    for name in targets:
        results.append(check_model(name))
    return results
