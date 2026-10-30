# dump_blueprint_trace.py
import traceback
from typing import Any

from flask import Blueprint, Flask

# Import your actual factory method
from app import create_app


class TracingFlask(Flask):
    def register_blueprint(
        self,
        blueprint: Blueprint,
        **options: Any,
    ) -> None:
        bp_name = getattr(blueprint, "name", "unknown")

        if bp_name in {"admin", "diagnostics"}:
            print(f"\n[🚨 INTERCEPT] Registering blueprint: '{bp_name}'")
            print("--------------------------------------------------")
            for frame in traceback.format_stack()[-5:-1]:
                print(frame.strip())
            print("--------------------------------------------------")

        super().register_blueprint(blueprint, **options)


print("🚀 TRACING BLUEPRINT REGISTRATIONS AT RUNTIME...")

# The factory must use this class when constructing the Flask app
app = create_app("testing", app_class=TracingFlask)