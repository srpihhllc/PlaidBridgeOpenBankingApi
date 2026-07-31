# dump_blueprint_trace.py
import traceback
from flask import Flask

# Import your actual factory method
from app import create_app

print("🚀 TRACING BLUEPRINT REGISTRATIONS AT RUNTIME...")

# Dynamically patch Flask.register_blueprint to intercept and print call stacks
_original_register = Flask.register_blueprint

def trace_register(self, blueprint, **options):
    bp_name = getattr(blueprint, 'name', 'unknown')
    if bp_name in ['admin', 'diagnostics']:
        print(f"\n[🚨 INTERCEPT] Registering blueprint: '{bp_name}'")
        print("--------------------------------------------------")
        # Print the last 4 frames of the call stack to see exactly where it called from
        for frame in traceback.format_stack()[-5:-1]:
            print(frame.strip())
        print("--------------------------------------------------")
    return _original_register(self, blueprint, **options)

Flask.register_blueprint = trace_register

# Invoke your application initialization matching your test environment
app = create_app("testing")