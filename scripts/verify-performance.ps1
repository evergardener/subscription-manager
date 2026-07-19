param([string]$PythonPath = 'python', [switch]$SkipBuild)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$project = 'subscription-manager-performance-validation'
$env:POSTGRES_PASSWORD = 'performance-validation-only'
$env:POSTGRES_DB = 'hermes_performance_validation'
$env:POSTGRES_USER = 'hermes'
$env:BACKEND_PORT = '18400'
$env:API_RATE_LIMIT_PER_MINUTE = '10000'
$env:LOGIN_RATE_LIMIT_PER_MINUTE = '100'
$baseUrl = 'http://localhost:18400'

try {
    $arguments = @('compose', '-p', $project, 'up', '-d')
    if (-not $SkipBuild) { $arguments += '--build' }
    $arguments += 'backend'
    & docker @arguments
    if ($LASTEXITCODE -ne 0) { throw 'Could not start the performance stack.' }
    $deadline = (Get-Date).AddMinutes(3)
    do {
        try {
            $ready = Invoke-RestMethod -Uri "$baseUrl/api/v1/health/ready" -TimeoutSec 3
            if ($ready.status -eq 'ok') { break }
        } catch {
            if ((Get-Date) -ge $deadline) { throw 'Performance backend did not become ready.' }
            Start-Sleep -Seconds 2
        }
    } while ($true)

    & docker compose -p $project cp (Join-Path $root 'scripts/performance-seed.sql') 'db:/tmp/performance-seed.sql'
    if ($LASTEXITCODE -ne 0) { throw 'Could not copy performance seed SQL.' }
    & docker compose -p $project exec -T db psql --username=$env:POSTGRES_USER --dbname=$env:POSTGRES_DB --set=ON_ERROR_STOP=1 --file=/tmp/performance-seed.sql
    if ($LASTEXITCODE -ne 0) { throw 'Performance seed failed.' }

    $web = New-Object Microsoft.PowerShell.Commands.WebRequestSession
    $credentials = @{ username = 'performance-admin'; password = 'performance-validation-password' } | ConvertTo-Json
    Invoke-RestMethod -Method Post -Uri "$baseUrl/api/v1/auth/bootstrap" -Body $credentials -ContentType 'application/json' -WebSession $web | Out-Null
    $login = Invoke-RestMethod -Method Post -Uri "$baseUrl/api/v1/auth/login" -Body $credentials -ContentType 'application/json' -WebSession $web
    $tokenPayload = @{
        name = 'Performance Gate'; actor_type = 'hermes'; actor_id = 'performance-gate'
        scopes = @('subscriptions:read', 'analytics:read')
    } | ConvertTo-Json
    $token = Invoke-RestMethod -Method Post -Uri "$baseUrl/api/v1/api-tokens" -Body $tokenPayload -ContentType 'application/json' -Headers @{ 'X-CSRF-Token' = $login.csrf_token } -WebSession $web
    & $PythonPath (Join-Path $root 'scripts/performance_gate.py') --base-url $baseUrl --token $token.token --samples 20
    if ($LASTEXITCODE -ne 0) { throw 'Performance P95 gate failed.' }
} finally {
    & docker compose -p $project down --volumes --remove-orphans
}
