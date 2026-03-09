"""
Deployment Readiness Test
Simulates staging-deploy.yml workflow checks locally
"""
import os
import sys
import subprocess
from pathlib import Path

# Add PlaidBridgeOpenBankingApi to Python path
sys.path.insert(0, str(Path(__file__).parent / "PlaidBridgeOpenBankingApi"))


def _read_env_keys(env_path: Path) -> set[str]:
    """Read KEY names from a dotenv-style file without loading values into process env."""
    keys: set[str] = set()
    if not env_path.exists():
        return keys

    for line in env_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        key = s.split("=", 1)[0].strip()
        if key:
            keys.add(key)
    return keys

def test_backend():
    """Test backend app creation (smoke test)"""
    print("=" * 60)
    print("BACKEND DEPLOYMENT TEST")
    print("=" * 60)
    
    try:
        from app import create_app
        app = create_app()
        
        route_count = len(list(app.url_map.iter_rules()))
        blueprint_count = len(app.blueprints)
        
        print(f"[OK] Backend app creation: SUCCESS")
        print(f"   - Total routes: {route_count}")
        print(f"   - Total blueprints: {blueprint_count}")
        print(f"   - Flask version: {app.__class__.__module__}")
        
        # Check critical blueprints
        critical_bps = ['api_v1', 'fintech', 'plaid', 'auth']
        missing = [bp for bp in critical_bps if bp not in app.blueprints]
        if missing:
            print(f"[WARN] Missing blueprints: {missing}")
        else:
            print(f"[OK] All critical blueprints registered")
        
        return True
    except Exception as e:
        print(f"[FAIL] Backend app creation: FAILED")
        print(f"   Error: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_mobile():
    """Test mobile app build readiness"""
    print("\n" + "=" * 60)
    print("MOBILE APP DEPLOYMENT TEST")
    print("=" * 60)
    
    mobile_path = Path(__file__).parent / "mobile-app"
    
    if not (mobile_path / "package.json").exists():
        print("[FAIL] Mobile app not found")
        return False
    
    try:
        # Check if pnpm is available
        pnpm_check = subprocess.run(
            ["pnpm", "--version"],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if pnpm_check.returncode != 0:
            print("[WARN] pnpm not installed, skipping mobile tests")
            return None
        
        print(f"[OK] pnpm version: {pnpm_check.stdout.strip()}")
        
        # Check package.json
        import json
        with open(mobile_path / "package.json") as f:
            package = json.load(f)
        
        print(f"[OK] Mobile app: {package.get('name', 'unknown')}")
        print(f"   - Version: {package.get('version', 'unknown')}")
        
        # Check for critical dependencies
        deps = package.get('dependencies', {})
        critical_deps = ['expo', '@trpc/react-query', 'react-native']
        for dep in critical_deps:
            if dep in deps:
                print(f"   - {dep}: {deps[dep]}")
            else:
                print(f"   [WARN] Missing {dep}")
        
        # Check if node_modules exists
        if (mobile_path / "node_modules").exists():
            print("[OK] Dependencies installed")
        else:
            print("[WARN] Dependencies not installed (run: cd mobile-app && pnpm install)")
        
        return True
    except Exception as e:
        print(f"[FAIL] Mobile app test: FAILED")
        print(f"   Error: {e}")
        return False

def test_environment():
    """Check environment configuration"""
    print("\n" + "=" * 60)
    print("ENVIRONMENT CONFIGURATION TEST")
    print("=" * 60)
    
    root = Path(__file__).parent
    
    # Check .env files
    backend_env = root / "PlaidBridgeOpenBankingApi" / ".env"
    mobile_env = root / "mobile-app" / ".env"
    
    print(f"Backend .env: {'[OK] EXISTS' if backend_env.exists() else '[FAIL] MISSING'}")
    print(f"Mobile .env:  {'[OK] EXISTS' if mobile_env.exists() else '[FAIL] MISSING'}")
    
    # Check .gitignore
    gitignore = root / ".gitignore"
    if gitignore.exists():
        content = gitignore.read_text()
        env_ignored = '.env' in content or '*.env' in content
        print(f".gitignore:   {'[OK] .env files ignored' if env_ignored else '[WARN] .env not ignored'}")
    
    # Read keys from backend .env so local checks match repository-secret usage.
    backend_env_keys = _read_env_keys(backend_env)

    # Primary variables aligned to current GitHub secrets inventory (DATABASE_URL is primary).
    primary_vars = [
        "SECRET_KEY",
        "JWT_SECRET_KEY",
        "DATABASE_URL",
        "PLAID_CLIENT_ID",
        "PLAID_SECRET",
        "REDIS_URL",
    ]

    print(f"\nPrimary environment variables ({len(primary_vars)}):")
    for var in primary_vars:
        has_value = (os.getenv(var) is not None) or (var in backend_env_keys)
        print(f"   {'[OK]' if has_value else '[WARN]'} {var}")

    # Optional component-mode DB vars (fallback if DATABASE_URL not used; supported by app/config.py).
    # Only show these if DATABASE_URL is not set (fallback mode).
    database_url_set = (os.getenv("DATABASE_URL") is not None) or ("DATABASE_URL" in backend_env_keys)
    
    component_db_vars = ["DB_USER", "DB_PASSWORD", "DB_HOST", "DB_NAME"]
    comp_count = sum(1 for var in component_db_vars if var in backend_env_keys or os.getenv(var) is not None)
    
    if comp_count and not database_url_set:
        print(f"\nOptional DB component variables (fallback): {comp_count}/4 present")
        for var in component_db_vars:
            has_value = (os.getenv(var) is not None) or (var in backend_env_keys)
            print(f"   {'[OK]' if has_value else '[WARN]'} {var}")
    elif comp_count:
        print(f"\nOptional DB component variables (DATABASE_URL takes precedence): {comp_count}/4 present")

    # Validate mobile env contains only EXPO_PUBLIC_* keys.
    if mobile_env.exists():
        mobile_keys = _read_env_keys(mobile_env)
        non_public_mobile_keys = sorted([k for k in mobile_keys if not k.startswith("EXPO_PUBLIC_")])
        if non_public_mobile_keys:
            print("\n[FAIL] Mobile .env contains non-public keys:")
            for key in non_public_mobile_keys:
                print(f"   - {key}")
            return False
        print("\n[OK] Mobile .env contains only EXPO_PUBLIC_* keys")
    
    return True

def test_git_status():
    """Check git repository status"""
    print("\n" + "=" * 60)
    print("GIT REPOSITORY STATUS")
    print("=" * 60)
    
    try:
        # Check current branch
        branch = subprocess.run(
            ["git", "branch", "--show-current"],
            capture_output=True,
            text=True,
            timeout=5
        )
        print(f"Current branch: {branch.stdout.strip()}")
        
        # Check if there are uncommitted changes
        status = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True,
            text=True,
            timeout=15
        )
        
        if status.stdout.strip():
            print("[WARN] Uncommitted changes detected:")
            for line in status.stdout.strip().split('\n')[:10]:
                print(f"   {line}")
        else:
            print("[OK] Working tree clean")
        
        # Check if ahead/behind remote
        tracking = subprocess.run(
            ["git", "rev-list", "--left-right", "--count", "origin/main...main"],
            capture_output=True,
            text=True,
            timeout=5
        )
        
        if tracking.returncode == 0:
            ahead, behind = tracking.stdout.strip().split()
            if ahead == "0" and behind == "0":
                print(f"[OK] In sync with origin/main")
            else:
                print(f"[WARN] Ahead: {ahead}, Behind: {behind}")

        return True
    except Exception as e:
        print(f"[WARN] Git status check failed: {e}")
        return False

def main():
    """Run all deployment tests"""
    print("\n" + "=" * 60)
    print("DEPLOYMENT READINESS TEST")
    print("Simulating: .github/workflows/staging-deploy.yml")
    print("=" * 60 + "\n")
    
    results = {
        'backend': test_backend(),
        'mobile': test_mobile(),
        'environment': test_environment(),
        'git': test_git_status()
    }
    
    print("\n" + "=" * 60)
    print("DEPLOYMENT READINESS SUMMARY")
    print("=" * 60)
    
    for component, status in results.items():
        if status is True:
            print(f"[OK] {component.upper()}: READY")
        elif status is False:
            print(f"[FAIL] {component.upper()}: NOT READY")
        else:
            print(f"[WARN] {component.upper()}: SKIPPED")
    
    all_ready = all(v in (True, None) for v in results.values())
    
    print("\n" + "=" * 60)
    if all_ready:
        print("[OK] DEPLOYMENT: READY FOR STAGING")
        print("=" * 60)
        print("\nNext steps:")
        print("1. Commit any pending changes")
        print("2. Push to 'staging' branch to trigger deployment workflow")
        print("3. Or use: gh workflow run staging-deploy.yml")
        return 0
    else:
        print("[FAIL] DEPLOYMENT: NOT READY")
        print("=" * 60)
        print("\nFix the issues above before deploying.")
        return 1

if __name__ == "__main__":
    sys.exit(main())
