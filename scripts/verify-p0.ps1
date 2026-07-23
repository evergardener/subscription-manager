param(
    [switch]$SkipInstall,
    [switch]$SkipCompose
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$env:UV_CACHE_DIR = Join-Path $root '.cache\uv'
$env:npm_config_cache = Join-Path $root '.cache\npm'

function Invoke-Step {
    param([string]$Name, [scriptblock]$Action)
    Write-Host "`n==> $Name" -ForegroundColor Cyan
    & $Action
    if ($LASTEXITCODE -ne 0) {
        throw "$Name failed with exit code $LASTEXITCODE"
    }
}

Push-Location (Join-Path $root 'backend')
try {
    if (-not $SkipInstall) {
        Invoke-Step 'Backend dependency sync' { uv sync --frozen }
    }
    Invoke-Step 'Backend lint' { uv run ruff check . }
    Invoke-Step 'Backend format check' { uv run ruff format --check . }
    Invoke-Step 'Backend type check' { uv run mypy app tests }
    Invoke-Step 'Backend tests' { uv run python -m pytest }
    Invoke-Step 'Alembic offline SQL generation' { uv run alembic upgrade head --sql }
    Invoke-Step 'P0 static configuration validation' { uv run python ..\scripts\validate_p0.py }
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
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        throw 'Docker is required for Compose validation. Re-run with -SkipCompose only for a partial local check.'
    }
    Push-Location $root
    try {
        $env:POSTGRES_PASSWORD = 'local-validation-only'
        Invoke-Step 'Compose config validation' { docker compose config --quiet }
    }
    finally {
        Pop-Location
    }
}

if ($SkipCompose) {
    Write-Warning 'Partial P0 verification completed; Compose runtime/config validation was skipped.'
}
else {
    Write-Host "`nFull P0 verification completed." -ForegroundColor Green
}
