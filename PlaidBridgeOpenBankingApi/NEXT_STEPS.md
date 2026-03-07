# Senior Dev Action Items — March 2026

## Immediate (This Week)
- [ ] Verify secret exposure risk and rotate any historical `.env` secrets if they were ever committed
- [ ] Ensure `.env` stays untracked (`git ls-files .env` should return empty)
- [ ] Review and merge PR #139 (WSGI/deploy fixes) if still open and valid
- [x] Keep `.coveragerc` with `app/cli/*` and `app/scripts/*` omitted from denominator
- [x] Lower coverage gate to temporary ramp target (`--cov-fail-under=40`)

## Sprint 1 (Next 2 Weeks)
- [ ] Write tests for `app/blueprints/auth_routes.py` (P0)
- [ ] Write tests for `app/security_utilities.py` (P0)
- [ ] Add app-factory focused coverage for `app/__init__.py` (P0)
- [ ] Rename `app/tests/tests_main_ routes.py` to `app/tests/test_main_routes.py`
- [ ] Remove or consolidate duplicate tests (`test_app.py` vs `test_balance.py`) after content diff
- [ ] Raise gate from 40 to 55 once green

## Sprint 2-3
- [ ] Cover `admin_routes.py`, `api_v1_routes.py`, and `fintech_routes.py`
- [ ] Expand `app/services/*` business-logic tests
- [ ] Raise gate to 70, then 85

## Hardening
- [ ] Keep CI workflows healthy (`.github/workflows/ci.yml`, `backend-ci.yml`, `mobile-ci.yml`)
- [ ] Add/validate `CODEOWNERS` and branch protection rules
- [ ] Add/validate `dependabot.yml`
