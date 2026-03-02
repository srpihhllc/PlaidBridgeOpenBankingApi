# (paste the file contents from above here)
def run():
    """
    Compatibility wrapper so scripts/audit.py can call ttl_audit.run().

    Implementation:
    - Find the Click Command object `ttl_audit`, get its .callback (the
      Click-wrapped function), unwrap to the original implementation via
      __wrapped__, and call that original function inside a Flask
      app_context (current_app if present, otherwise a temporary app).
    - Use the default domain 'boot'.
    """
    cmd = globals().get("ttl_audit")
    if cmd is None:
        print("[SKIP] ttl_audit command not found in module.")
        return

    callback = getattr(cmd, "callback", None)
    if not callable(callback):
        print("[SKIP] ttl_audit.callback not callable; skipping.")
        return

    # Unwrap decorated function to underlying implementation
    fn = callback
    while hasattr(fn, "__wrapped__"):
        fn = fn.__wrapped__

    def _invoke(domain="boot"):
        try:
            fn(domain)
        except TypeError:
            # Fallback if signature differs (no-arg)
            fn()

    # Try to run inside existing Flask app context
    try:
        # Access current_app to assert we're in an app context (raises if not)
        from flask import current_app as _current_app  # local import to avoid top-level coupling
        _ = _current_app._get_current_object()
        _invoke("boot")
        return
    except RuntimeError:
        # No current_app — create a temporary app and run inside its context
        try:
            from app import create_app
        except Exception:
            print("[SKIP] create_app unavailable; cannot run ttl_audit.")
            return

        app = create_app()
        with app.app_context():
            try:
                _invoke("boot")
            except Exception as e:
                print(f"[ERROR] ttl_audit underlying function raised: {e}")
