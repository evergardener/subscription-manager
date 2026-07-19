param(
    [Parameter(Mandatory = $true)][string]$BackupPath,
    [string]$ProjectName = 'subscription-manager-restore-validation',
    [switch]$SkipBuild
)

$ErrorActionPreference = 'Stop'
if ($ProjectName -notmatch 'restore-validation$') { throw 'The project name must end in restore-validation.' }
$backup = (Resolve-Path -LiteralPath $BackupPath).Path
$hashPath = "$backup.sha256"
if (-not (Test-Path -LiteralPath $hashPath)) { throw 'The SHA-256 sidecar is required.' }
$expectedHash = ((Get-Content -LiteralPath $hashPath -Raw).Trim() -split '\s+')[0]
$actualHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $backup).Hash.ToLowerInvariant()
if ($actualHash -ne $expectedHash.ToLowerInvariant()) { throw 'Backup SHA-256 verification failed.' }

$env:POSTGRES_PASSWORD = 'restore-validation-only'
$env:POSTGRES_DB = 'hermes_restore_validation'
$env:POSTGRES_USER = 'hermes'
$env:BACKEND_PORT = '18200'
$containerPath = '/tmp/hermes-restore-validation.dump'

try {
    & docker compose -p $ProjectName up -d db
    if ($LASTEXITCODE -ne 0) { throw 'Could not start the restore database.' }
    $deadline = (Get-Date).AddMinutes(2)
    do {
        & docker compose -p $ProjectName exec -T db pg_isready --username=$env:POSTGRES_USER --dbname=$env:POSTGRES_DB | Out-Null
        if ($LASTEXITCODE -eq 0) { break }
        if ((Get-Date) -ge $deadline) { throw 'Restore database did not become ready.' }
        Start-Sleep -Seconds 2
    } while ($true)

    & docker compose -p $ProjectName cp $backup "db:$containerPath"
    if ($LASTEXITCODE -ne 0) { throw 'Could not copy the backup into the restore database.' }
    & docker compose -p $ProjectName exec -T db pg_restore --exit-on-error --no-owner --no-privileges --username=$env:POSTGRES_USER --dbname=$env:POSTGRES_DB $containerPath
    if ($LASTEXITCODE -ne 0) { throw 'pg_restore failed.' }

    $arguments = @('compose', '-p', $ProjectName, 'up', '-d')
    if (-not $SkipBuild) { $arguments += '--build' }
    $arguments += 'backend'
    & docker @arguments
    if ($LASTEXITCODE -ne 0) { throw 'Could not start the restored backend.' }
    $readyDeadline = (Get-Date).AddMinutes(3)
    do {
        try {
            $ready = Invoke-RestMethod -Uri 'http://localhost:18200/api/v1/health/ready' -TimeoutSec 3
            if ($ready.status -eq 'ok') { break }
        } catch {
            if ((Get-Date) -ge $readyDeadline) { throw 'Restored backend did not become ready.' }
            Start-Sleep -Seconds 2
        }
    } while ($true)

    $requiredTables = @('users', 'subscriptions', 'billing_plans', 'billing_events', 'payments', 'audit_logs', 'alembic_version')
    foreach ($table in $requiredTables) {
        $exists = & docker compose -p $ProjectName exec -T db psql --username=$env:POSTGRES_USER --dbname=$env:POSTGRES_DB --tuples-only --no-align --command="SELECT to_regclass('public.$table') IS NOT NULL"
        if ($LASTEXITCODE -ne 0 -or $exists.Trim() -ne 't') { throw "Required table $table is missing after restore." }
    }
    $version = & docker compose -p $ProjectName exec -T db psql --username=$env:POSTGRES_USER --dbname=$env:POSTGRES_DB --tuples-only --no-align --command='SELECT version_num FROM alembic_version'
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($version)) { throw 'Migration version verification failed.' }
    $subscriptionCount = & docker compose -p $ProjectName exec -T db psql --username=$env:POSTGRES_USER --dbname=$env:POSTGRES_DB --tuples-only --no-align --command='SELECT count(*) FROM subscriptions'
    if ($LASTEXITCODE -ne 0) { throw 'Core subscription query failed after restore.' }
    Write-Output "Restore verification passed: migration=$($version.Trim()) subscriptions=$($subscriptionCount.Trim())"
} finally {
    & docker compose -p $ProjectName down --volumes --remove-orphans
}
