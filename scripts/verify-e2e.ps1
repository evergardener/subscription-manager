param([switch]$SkipBuild)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$project = 'subscription-manager-e2e'
$env:POSTGRES_PASSWORD = 'e2e-validation-only'
$env:POSTGRES_DB = 'hermes_e2e'
$env:BACKEND_PORT = '18000'
$env:FRONTEND_PORT = '18080'
$env:E2E_BASE_URL = 'http://localhost:18080'

try {
    $arguments = @('compose', '-p', $project, 'up', '-d')
    if (-not $SkipBuild) { $arguments += '--build' }
    $arguments += @('backend', 'frontend')
    & docker @arguments
    if ($LASTEXITCODE -ne 0) { throw 'Could not start the isolated E2E stack.' }

    $deadline = (Get-Date).AddMinutes(3)
    do {
        try {
            $response = Invoke-WebRequest -UseBasicParsing "$env:E2E_BASE_URL/api/v1/health/ready" -TimeoutSec 3
            if ($response.StatusCode -eq 200) { break }
        } catch {
            if ((Get-Date) -ge $deadline) { throw 'The isolated E2E stack did not become ready.' }
            Start-Sleep -Seconds 2
        }
    } while ($true)

    Push-Location (Join-Path $root 'frontend')
    try {
        npm run test:e2e
        if ($LASTEXITCODE -ne 0) { throw 'Playwright E2E tests failed.' }
    } finally {
        Pop-Location
    }
} finally {
    & docker compose -p $project down --volumes --remove-orphans
}
