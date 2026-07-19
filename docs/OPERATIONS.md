# Production Operations Runbook

## Deployment models

Use `deploy/compose.production.yml` for bundled PostgreSQL or `deploy/compose.external-db.yml` with a PostgreSQL 16+ `DATABASE_URL`. Both expose only Frontend to the external Traefik network; Backend and the bundled database remain on an internal Docker network.

Required production choices are supplied through `.env`, never committed:

- `HERMES_DOMAIN`: public DNS name routed to Traefik.
- `POSTGRES_PASSWORD`, or TLS-enabled `DATABASE_URL` for an external database.
- `TRAEFIK_NETWORK` and `TRAEFIK_CERT_RESOLVER` matching the existing Traefik deployment.
- `NTFY_TOPIC` and optionally a private `NTFY_BASE_URL` before real notifications are enabled.

Start bundled PostgreSQL deployment:

```bash
docker compose --env-file .env -f deploy/compose.production.yml -p hermes-subscription-manager config --quiet
docker compose --env-file .env -f deploy/compose.production.yml -p hermes-subscription-manager up -d --build
```

The migration container must exit successfully before Backend starts. Require Backend and database health checks to pass before bootstrap or login.

## systemd

Copy the repository to `/opt/hermes-subscription-manager`, protect `.env` with mode `0600`, and install the units from `deploy/systemd/` under `/etc/systemd/system/`. Then run:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now hermes-subscription-manager.service
sudo systemctl enable --now hermes-backup.timer
systemctl list-timers hermes-backup.timer
```

The timer runs daily at approximately 02:15 and retains seven days by default. Configure encrypted off-host replication separately and test a restore regularly using [BACKUP_RESTORE.md](BACKUP_RESTORE.md).

## Routine operations

- Health: `docker compose ... ps` and `/api/v1/health/live`, `/api/v1/health/ready`.
- Logs: `docker compose ... logs --since 30m backend scheduler`; correlate failures with `request_id` and audit entries.
- Upgrade: create and verify a backup, fetch the reviewed revision, run `compose up -d --build`, and confirm migration/ready/core UI before starting normal use.
- Rollback: do not downgrade application code across a migration without a verified compatible database backup. Restore into a new database and switch `DATABASE_URL` after validation.
- Password recovery: `docker compose ... exec backend python -m app.cli reset-admin-password --username <name>`.
- Token rotation: create the replacement with minimum scopes, update the client secret, verify it, then revoke the old Token in Settings.
- Notification failure: inspect Scheduler logs and reminder deliveries; verify `NTFY_BASE_URL`/topic connectivity without logging credentials. Keep Scheduler stopped during disaster recovery until data validation finishes.

Only one Scheduler instance may run. Do not scale the `scheduler` service. Backend may be scaled behind Frontend after moving rate limiting to a shared gateway policy; the built-in in-memory limiter is per Backend process.
