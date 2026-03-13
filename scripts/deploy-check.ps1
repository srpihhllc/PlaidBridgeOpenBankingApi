# Enterprise Deployment - Quick Setup Script
# Run this after configuring GitHub secrets

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "PlaidBridge Enterprise Deployment" -ForegroundColor Green
Write-Host "========================================`n" -ForegroundColor Cyan

# Check prerequisites
Write-Host "Checking prerequisites..." -ForegroundColor Yellow

$Prerequisites = @{
    "GitHub CLI" = { gh --version }
    "Docker" = { docker --version }
    "Python" = { python --version }
    "Git" = { git --version }
}

foreach ($tool in $Prerequisites.Keys) {
    try {
        $null = & $Prerequisites[$tool] 2>&1
        Write-Host "  [OK] $tool installed" -ForegroundColor Green
    }
    catch {
        Write-Host "  [FAIL] $tool NOT installed" -ForegroundColor Red
    }
}

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "Checking GitHub Secrets..." -ForegroundColor Yellow
Write-Host "========================================`n" -ForegroundColor Cyan

$RequiredSecrets = @(
    "SECRET_KEY",
    "JWT_SECRET_KEY",
    "DATABASE_URL",
    "PLAID_CLIENT_ID",
    "PLAID_SECRET",
    "PLAID_PUBLIC_KEY",
    "PLAID_ENV",
    "REDIS_URL",
    "TREASURY_PRIME_ENV",
    "TREASURY_PRIME_PRODUCTION_API_KEY",
    "TREASURY_PRIME_PRODUCTION_API_URL",
    "TREASURY_PRIME_SANDBOX_API_KEY",
    "TREASURY_PRIME_SANDBOX_API_URL",
    "USER_EMAIL",
    "USER_PASSWORD",
    "ACCOUNT_NUMBER"
)

try {
    $ConfiguredSecrets = gh secret list 2>&1 | Out-String
    
    foreach ($secret in $RequiredSecrets) {
        if ($ConfiguredSecrets -match $secret) {
            Write-Host "  [OK] $secret" -ForegroundColor Green
        }
        else {
            Write-Host "  [FAIL] $secret (MISSING)" -ForegroundColor Red
        }
    }
}
catch {
    Write-Host "  [WARN] Unable to check secrets. Run: gh auth login" -ForegroundColor Yellow
}

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "Deployment Options" -ForegroundColor Yellow
Write-Host "========================================`n" -ForegroundColor Cyan

Write-Host "1. Deploy to STAGING:" -ForegroundColor Cyan
Write-Host "   git checkout -b staging" -ForegroundColor White
Write-Host "   git push origin staging`n" -ForegroundColor White

Write-Host "2. Deploy to PRODUCTION:" -ForegroundColor Cyan
Write-Host "   git checkout -b production" -ForegroundColor White
Write-Host "   git merge main" -ForegroundColor White
Write-Host "   git push origin production`n" -ForegroundColor White

Write-Host "3. Deploy with VERSION TAG:" -ForegroundColor Cyan
Write-Host "   git tag -a v1.0.0 -m 'Production release 1.0.0'" -ForegroundColor White
Write-Host "   git push origin v1.0.0`n" -ForegroundColor White

Write-Host "4. Manual Workflow Trigger:" -ForegroundColor Cyan
Write-Host "   gh workflow run production-deploy.yml`n" -ForegroundColor White

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "Documentation" -ForegroundColor Yellow
Write-Host "========================================`n" -ForegroundColor Cyan

Write-Host "  - ENTERPRISE_DEPLOYMENT_GUIDE.md - Full deployment guide"
Write-Host "  - GITHUB_SECRETS_SETUP_GUIDE.md - Secrets configuration"
Write-Host "  - DEPLOYMENT_TEST_REPORT.md - Local test results"
Write-Host "  - CREDENTIAL_ROTATION_GUIDE.md - Security procedures`n"

Write-Host "========================================`n" -ForegroundColor Cyan
