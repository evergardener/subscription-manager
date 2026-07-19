param([switch]$SkipBuild)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$sourceProject = 'subscription-manager-backup-source-validation'
$env:POSTGRES_PASSWORD = 'backup-source-validation-only'
$env:POSTGRES_DB = 'hermes_backup_validation'
$env:POSTGRES_USER = 'hermes'
$env:BACKEND_PORT = '18300'
$tempRoot = [System.IO.Path]::GetFullPath([System.IO.Path]::GetTempPath())
$workDirectory = Join-Path $tempRoot ('hermes-backup-restore-' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $workDirectory | Out-Null

try {
    $arguments = @('compose', '-p', $sourceProject, 'up', '-d')
    if (-not $SkipBuild) { $arguments += '--build' }
    $arguments += 'backend'
    & docker @arguments
    if ($LASTEXITCODE -ne 0) { throw 'Could not start the backup source stack.' }
    $deadline = (Get-Date).AddMinutes(3)
    do {
        try {
            $ready = Invoke-RestMethod -Uri 'http://localhost:18300/api/v1/health/ready' -TimeoutSec 3
            if ($ready.status -eq 'ok') { break }
        } catch {
            if ((Get-Date) -ge $deadline) { throw 'Backup source backend did not become ready.' }
            Start-Sleep -Seconds 2
        }
    } while ($true)

    $web = New-Object Microsoft.PowerShell.Commands.WebRequestSession
    $credentials = @{ username = 'backup-admin'; password = 'backup-validation-password' } | ConvertTo-Json
    Invoke-RestMethod -Method Post -Uri 'http://localhost:18300/api/v1/auth/bootstrap' -Body $credentials -ContentType 'application/json' -WebSession $web | Out-Null
    $login = Invoke-RestMethod -Method Post -Uri 'http://localhost:18300/api/v1/auth/login' -Body $credentials -ContentType 'application/json' -WebSession $web
    $subscription = @{
        name = 'Backup Restore Evidence'; status = 'active'
        billing_plan = @{
            amount = '42.00'; currency = 'USD'; interval_unit = 'month'; interval_count = 1
            anchor_date = '2026-08-19'; next_billing_date = '2026-08-19'; auto_renew = $true; billing_mode = 'fixed'
        }
    } | ConvertTo-Json -Depth 5
    Invoke-RestMethod -Method Post -Uri 'http://localhost:18300/api/v1/subscriptions' -Body $subscription -ContentType 'application/json' -Headers @{ 'X-CSRF-Token' = $login.csrf_token; 'Idempotency-Key' = 'backup-restore-evidence' } -WebSession $web | Out-Null

    $backup = . (Join-Path $root 'scripts/backup-postgres.ps1') -ProjectName $sourceProject -OutputDirectory $workDirectory -Database $env:POSTGRES_DB -User $env:POSTGRES_USER
    . (Join-Path $root 'scripts/verify-restore.ps1') -BackupPath $backup -SkipBuild:$SkipBuild
} finally {
    & docker compose -p $sourceProject down --volumes --remove-orphans
    $resolved = [System.IO.Path]::GetFullPath($workDirectory)
    if (-not $resolved.StartsWith($tempRoot, [System.StringComparison]::OrdinalIgnoreCase) -or -not (Split-Path -Leaf $resolved).StartsWith('hermes-backup-restore-')) {
        throw 'Refusing to clean an unexpected backup verification path.'
    }
    Remove-Item -LiteralPath $resolved -Recurse -Force
}
