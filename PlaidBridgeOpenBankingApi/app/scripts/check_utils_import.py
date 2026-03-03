#!/usr/bin/env python3
import importlib, traceback, sys

try:
    m = importlib.import_module("app.utils")
    print("app.utils __file__:", getattr(m, "__file__", None))
    print("nav_audit present on package:", hasattr(m, "nav_audit"))
    try:
        na = importlib.import_module("app.utils.nav_audit")
        print("nav_audit module __file__:", getattr(na, "__file__", None))
        print("nav_audit has run()?:", hasattr(na, "run"), "callable?:", callable(getattr(na, "run", None)))
    except Exception as e:
        print("Direct import of app.utils.nav_audit failed:", e)
        traceback.print_exc()
except Exception as e:
    print("Import of app.utils failed:", e)
    traceback.print_exc()
    sys.exit(2)
