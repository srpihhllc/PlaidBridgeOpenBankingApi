# Senior Dev Action Items — immediate checklist

## 🔴 Immediate (This Week)
- [ ] Rotate secrets and remove tracked .env (git rm --cached .env + commit + push)
- [ ] Add .coveragerc to exclude CLI/scripts/tests from coverage
- [ ] Temporarily lower coverage gate or run CI without coverage-fail-under during remediation

## 🟡 Short-term (1–2 sprints)
- [ ] Add CI workflow to run tests + audits and upload artifacts
- [ ] Write tests for P0 modules: app/__init__.py, app/blueprints/auth_routes.py, app/security_utilities.py
- [ ] Fix filename issues and duplicates in tests (rename `tests_main_ routes.py`, remove duplicates)

## 🟢 Medium-term
- [ ] Incrementally raise coverage (40% → 55% → 70% → 85%)
- [ ] Add CODEOWNERS and branch protection
- [ ] Integrate dependabot and security scans into PR process
