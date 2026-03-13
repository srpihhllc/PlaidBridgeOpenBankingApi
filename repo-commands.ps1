# 1) ensure you're in the repo folder (you said venv shows repo name)
Set-Location 'C:\Users\R\PlaidBridgeOpenBankingApi'

# 2) ensure PYTHONPATH includes the nested package directory so `import app` resolves
$env:PYTHONPATH = "$PWD\PlaidBridgeOpenBankingApi;$env:PYTHONPATH"

# 3) run the single failing test (fast, no coverage plugin)
python -m pytest PlaidBridgeOpenBankingApi/app/tests/test_auth_routes.py::test_mfa_prompt_redirects -q -p no:pytest_cov

# 4) run that test with verbose output (if you need tracebacks)
python -m pytest PlaidBridgeOpenBankingApi/app/tests/test_auth_routes.py::test_mfa_prompt_redirects -q -vv -p no:pytest_cov

# 5) run full test suite (slower)
python -m pytest -q -p no:pytest_cov

# 6) run alembic dry-run SQL to check migrations (won't touch DB)
python -m alembic -c PlaidBridgeOpenBankingApi/migrations/alembic.ini upgrade head --sql

# 7) run the Flask app locally (development):
$env:FLASK_APP = 'PlaidBridgeOpenBankingApi.app:create_app'
$env:FLASK_ENV = 'development'
flask run

# 8) when done, deactivate the venv
deactivate
