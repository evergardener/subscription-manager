# Backup and Restore Runbook

## Create a backup

Run on the application host while PostgreSQL is healthy:

```powershell
./scripts/backup-postgres.ps1 -ProjectName hermes-subscription-manager -RetentionDays 7
```

The command creates a PostgreSQL custom-format dump and a `.sha256` sidecar under `backups/`. The directory and dump formats are ignored by Git. The cleanup step removes only matching `hermes-*.dump` files older than the configured retention period from the exact output directory.

Schedule this command daily. Keep at least one encrypted copy outside the application host. Suitable options include an encrypted backup volume, an encrypted object-storage bucket, or encrypting each dump with age/GPG before upload. Encryption keys must not be stored beside the backups or committed to this repository.

## Verify or restore

Test a dump in a disposable empty database:

```powershell
./scripts/verify-restore.ps1 -BackupPath ./backups/hermes-YYYYMMDDTHHMMSSZ.dump
```

The verifier requires the SHA-256 sidecar, restores only into an isolated Compose project whose name ends in `restore-validation`, runs migrations, starts Backend, checks `/health/ready`, verifies required tables and the Alembic revision, and performs a core subscription query. Its temporary database volume is removed afterward.

For a real disaster recovery:

1. Stop Backend and Scheduler so no writes occur.
2. Preserve the failed database volume; do not overwrite the only copy.
3. Provision an empty PostgreSQL 16 database with a least-privilege application role.
4. Verify the sidecar hash, then run `pg_restore --exit-on-error --no-owner --no-privileges` into the empty database.
5. Point `DATABASE_URL` at the restored database and run `alembic upgrade head`.
6. Start Backend only and require `/api/v1/health/ready` to return 200.
7. Check administrator login, subscription count, upcoming events, payments, and audit history before starting Scheduler.
8. Record the backup timestamp, restore duration, migration revision, and validation result.

Never test recovery by restoring over the live database. For an external PostgreSQL service, use the provider's TLS connection settings and the same `pg_dump`/`pg_restore` flags; the bundled scripts target the Compose `db` service.
