param(
    [switch]$SkipInstall,
    [switch]$SkipCompose
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$env:UV_CACHE_DIR = Join-Path $root '.cache\uv'
$env:npm_config_cache = Join-Path $root '.cache\npm'

if (-not $env:TEST_DATABASE_URL) {
    throw 'TEST_DATABASE_URL is required and must point to a disposable PostgreSQL test database.'
}
if ($env:TEST_DATABASE_URL -notmatch '(test|validation)(\?|$)') {
    throw 'Refusing to run database integration checks unless the database name ends in test or validation.'
}
$env:DATABASE_URL = $env:TEST_DATABASE_URL

function Invoke-Step {
    param([string]$Name, [scriptblock]$Action)
    Write-Host "`n==> $Name" -ForegroundColor Cyan
    & $Action
    if ($LASTEXITCODE -ne 0) {
        throw "$Name failed with exit code $LASTEXITCODE"
    }
}

function Invoke-BackendTool {
    param([string]$Tool, [string[]]$Arguments)
    if (Get-Command uv -ErrorAction SilentlyContinue) {
        & uv run $Tool @Arguments
        return
    }
    $executable = Join-Path $root "backend\.venv\Scripts\$Tool.exe"
    if (-not (Test-Path $executable)) {
        throw "Neither uv nor the backend virtual-environment tool '$Tool' is available."
    }
    & $executable @Arguments
}

Push-Location (Join-Path $root 'backend')
try {
    if (-not $SkipInstall) {
        Invoke-Step 'Backend dependency sync' { uv sync --frozen }
    }
    Invoke-Step 'Backend lint' { Invoke-BackendTool ruff @('check', '.') }
    Invoke-Step 'Backend format check' { Invoke-BackendTool ruff @('format', '--check', '.') }
    Invoke-Step 'Backend type check' { Invoke-BackendTool mypy @('app', 'tests') }
    Invoke-Step 'P1-P3 tests and coverage' {
        Invoke-BackendTool pytest @('--cov=app.domain', '--cov=app.services', '--cov-report=term', '--cov-fail-under=80')
    }
    Invoke-Step 'Migration metadata drift check' { Invoke-BackendTool alembic @('check') }
    Invoke-Step 'Migration downgrade' { Invoke-BackendTool alembic @('downgrade', 'base') }
    Invoke-Step 'Migration upgrade' { Invoke-BackendTool alembic @('upgrade', 'head') }
    Invoke-Step 'Architecture validation' { Invoke-BackendTool python @('..\scripts\validate_p0.py') }
}
finally {
    Pop-Location
}

Push-Location (Join-Path $root 'frontend')
try {
    if (-not $SkipInstall) {
        Invoke-Step 'Frontend dependency install' { npm ci }
    }
    Invoke-Step 'Frontend dependency audit' { npm audit --audit-level=high }
    Invoke-Step 'Frontend lint' { npm run lint }
    Invoke-Step 'Frontend type check' { npm run typecheck }
    Invoke-Step 'Frontend tests' { npm test }
    Invoke-Step 'Frontend build' { npm run build }
}
finally {
    Pop-Location
}

if (-not $SkipCompose) {
    $env:POSTGRES_PASSWORD = 'local-validation-only'
    Invoke-Step 'Compose config validation' { docker compose -f (Join-Path $root 'compose.yml') config --quiet }
}

Write-Host "`nP1-P3 verification completed." -ForegroundColor Green
