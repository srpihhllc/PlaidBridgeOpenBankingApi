- Summary of changes:
  - Align template url_for endpoints to registered routes (admin_ui.* -> admin.* and a few specific corrections).
  - Expose Flask app in Jinja globals: flask_app.jinja_env.globals['app'] = flask_app
  - Fix auth login invalid-credentials behavior to re-render login page (HTTP 200).
- Verification steps:
  1. Set env:
     export PYTHONPATH="$PWD/PlaidBridgeOpenBankingApi"
     export FLASK_ENV=development
     export SQLALCHEMY_DATABASE_URI="sqlite:///./dev-db.sqlite"
  2. Run template audit:
     python -m app.scripts.audit
     Verify no missing endpoints for the templates being changed.
  3. Run tests:
     pytest -q app/tests/test_auth_routes.py::test_login_invalid_credentials
     pytest -q  # or CI run
  4. Manual smoke tests in staging:
     - Log in as admin and verify admin sidebar links and active states.
     - Open Trace Viewer and export a trace.
     - Open Dispute panel and verify links.
- Merge criteria:
  - CI green (unit tests + lint)
  - Code review approvals from backend lead and UI/template owner
- Rollback:
  - If a problem is found in staging, revert the merge commit: git revert <merge-commit-sha>
  - Or re-deploy previous tag and run rollback playbook
