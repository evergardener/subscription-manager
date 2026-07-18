param([string]$PythonPath = 'python', [switch]$SkipBuild)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$project = 'subscription-manager-hermes-e2e'
$env:POSTGRES_PASSWORD = 'hermes-e2e-validation-only'
$env:POSTGRES_DB = 'hermes_e2e'
$env:BACKEND_PORT = '18100'
$env:FRONTEND_PORT = '18180'
$baseUrl = 'http://localhost:18180'

try {
    $arguments = @('compose', '-p', $project, 'up', '-d')
    if (-not $SkipBuild) { $arguments += '--build' }
    $arguments += @('backend', 'frontend')
    & docker @arguments
    if ($LASTEXITCODE -ne 0) { throw 'Could not start the isolated Hermes stack.' }

    $deadline = (Get-Date).AddMinutes(3)
    do {
        try {
            $response = Invoke-WebRequest -UseBasicParsing "$baseUrl/api/v1/health/ready" -TimeoutSec 3
            if ($response.StatusCode -eq 200) { break }
        } catch {
            if ((Get-Date) -ge $deadline) { throw 'The isolated Hermes stack did not become ready.' }
            Start-Sleep -Seconds 2
        }
    } while ($true)

    $web = New-Object Microsoft.PowerShell.Commands.WebRequestSession
    $credentials = @{ username = 'hermes-e2e-admin'; password = 'hermes-e2e-admin-password' } | ConvertTo-Json
    Invoke-RestMethod -Method Post -Uri "$baseUrl/api/v1/auth/bootstrap" -Body $credentials -ContentType 'application/json' -WebSession $web | Out-Null
    $login = Invoke-RestMethod -Method Post -Uri "$baseUrl/api/v1/auth/login" -Body $credentials -ContentType 'application/json' -WebSession $web
    $tokenRequest = @{
        name = 'Hermes E2E'
        actor_type = 'hermes'
        actor_id = 'hermes-e2e'
        scopes = @('subscriptions:read', 'subscriptions:write', 'payments:write', 'analytics:read', 'audit:read')
    } | ConvertTo-Json
    $tokenResponse = Invoke-RestMethod -Method Post -Uri "$baseUrl/api/v1/api-tokens" -Body $tokenRequest -ContentType 'application/json' -Headers @{ 'X-CSRF-Token' = $login.csrf_token } -WebSession $web

    $env:HERMES_SUBSCRIPTION_API_URL = $baseUrl
    $env:HERMES_SUBSCRIPTION_API_TOKEN = $tokenResponse.token
    $createArguments = @{
        name = 'Hermes E2E Subscription'
        status = 'active'
        billing_plan = @{
            amount = '19.00'; currency = 'USD'; interval_unit = 'month'; interval_count = 1
            anchor_date = '2026-08-19'; next_billing_date = '2026-08-19'; auto_renew = $true; billing_mode = 'fixed'
        }
    } | ConvertTo-Json -Depth 5 -Compress
    $createOutput = & $PythonPath (Join-Path $root 'hermes/scripts/call_tool.py') subscription_create --arguments $createArguments --confirm
    if ($LASTEXITCODE -ne 0) { throw 'Hermes create tool failed.' }
    $created = $createOutput | ConvertFrom-Json
    if (-not $created.ok) { throw 'Hermes create tool returned an error.' }

    $getArguments = @{ subscription_id = $created.result.id } | ConvertTo-Json -Compress
    $getOutput = & $PythonPath (Join-Path $root 'hermes/scripts/call_tool.py') subscription_get --arguments $getArguments
    if ($LASTEXITCODE -ne 0 -or -not ($getOutput | ConvertFrom-Json).ok) { throw 'Hermes get tool failed.' }

    $audit = Invoke-RestMethod -Uri "$baseUrl/api/v1/audit-logs?page_size=100" -Headers @{ Authorization = "Bearer $($tokenResponse.token)" }
    $entry = $audit.items | Where-Object { $_.entity_id -eq $created.result.id -and $_.action -eq 'create' } | Select-Object -First 1
    if (-not $entry -or $entry.actor_type -ne 'hermes' -or $entry.actor_id -ne 'hermes-e2e') {
        throw 'Hermes audit identity verification failed.'
    }
    Write-Output 'Hermes isolated API verification passed.'
} finally {
    $env:HERMES_SUBSCRIPTION_API_TOKEN = $null
    & docker compose -p $project down --volumes --remove-orphans
}
