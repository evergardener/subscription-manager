param(
    [string]$ProjectName = 'subscription-manager',
    [string]$OutputDirectory = '',
    [int]$RetentionDays = 7,
    [string]$Database = $(if ($env:POSTGRES_DB) { $env:POSTGRES_DB } else { 'subscription_manager' }),
    [string]$User = $(if ($env:POSTGRES_USER) { $env:POSTGRES_USER } else { 'subscription_manager' })
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
if (-not $OutputDirectory) { $OutputDirectory = Join-Path $root 'backups' }
if ($RetentionDays -lt 1) { throw 'RetentionDays must be at least 1.' }
$directory = [System.IO.Path]::GetFullPath($OutputDirectory)
if ($directory -eq [System.IO.Path]::GetPathRoot($directory)) { throw 'Refusing to use a filesystem root as the backup directory.' }
New-Item -ItemType Directory -Force -Path $directory | Out-Null

$timestamp = (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ')
$name = "subscription-manager-$timestamp.dump"
$containerPath = "/tmp/$name"
$outputPath = Join-Path $directory $name

try {
    & docker compose -p $ProjectName exec -T db pg_dump --format=custom --compress=9 --no-owner --no-privileges --username=$User --dbname=$Database --file=$containerPath
    if ($LASTEXITCODE -ne 0) { throw 'pg_dump failed.' }
    & docker compose -p $ProjectName cp "db:$containerPath" $outputPath
    if ($LASTEXITCODE -ne 0) { throw 'Could not copy the database dump from the container.' }
} finally {
    & docker compose -p $ProjectName exec -T db rm -f $containerPath | Out-Null
}

$hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $outputPath).Hash.ToLowerInvariant()
Set-Content -LiteralPath "$outputPath.sha256" -Value "$hash  $name" -Encoding ascii
$cutoff = (Get-Date).ToUniversalTime().AddDays(-$RetentionDays)
Get-ChildItem -LiteralPath $directory -File -Filter 'subscription-manager-*.dump' |
    Where-Object { $_.LastWriteTimeUtc -lt $cutoff } |
    ForEach-Object {
        $expiredDump = $_.FullName
        $expiredHash = "$expiredDump.sha256"
        Remove-Item -LiteralPath $expiredDump
        if (Test-Path -LiteralPath $expiredHash) { Remove-Item -LiteralPath $expiredHash }
    }

Write-Output $outputPath
