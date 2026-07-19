# Production Operations Runbook

## Deployment boundary

Use `deploy/compose.production.yml` for bundled PostgreSQL or `deploy/compose.external-db.yml` with a PostgreSQL 16+ `DATABASE_URL`. The application stack contains only its database (when bundled), migration job, Backend, Scheduler, and Frontend. It does not install or configure a reverse proxy, DNS, certificates, ntfy, or provider-specific notification services.

Only Frontend is published, on `127.0.0.1:8080` by default. Frontend proxies `/api/v1` to the internal Backend; Backend and bundled PostgreSQL publish no host ports. Copy the matching example before deployment:

```bash
cp deploy/.env.production.example .env
# or: cp deploy/.env.external-db.example .env
chmod 0600 .env
```

At minimum, replace `POSTGRES_PASSWORD` for bundled PostgreSQL or `DATABASE_URL` for an external database. URL-encode reserved characters in database credentials. For external PostgreSQL, require TLS according to the provider's instructions.

New installations default to database and role name `subscription_manager`. Changing `POSTGRES_DB` or `POSTGRES_USER` does not rename objects inside an existing PostgreSQL volume; preserve the values used when that volume was initialized unless performing a separately planned database migration.

Start bundled PostgreSQL deployment:

```bash
docker compose --env-file .env -f deploy/compose.production.yml -p subscription-manager config --quiet
docker compose --env-file .env -f deploy/compose.production.yml -p subscription-manager up -d --build
```

For the external database, replace the Compose filename with `deploy/compose.external-db.yml`. The migration container must exit successfully before Backend starts. Require Backend and Frontend health checks to pass before bootstrap or login.

## Environment variables

| Variable | Meaning |
| --- | --- |
| `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` | Bundled PostgreSQL database, role, and secret. Only used by the bundled deployment. |
| `DATABASE_URL` | Complete SQLAlchemy PostgreSQL URL for the external-database deployment. |
| `SERVICE_BIND_ADDRESS`, `SERVICE_PORT` | Host address/port publishing Frontend. Keep loopback unless direct network exposure is deliberate and protected. |
| `LOG_LEVEL` | Backend and Scheduler log threshold. |
| `SESSION_ABSOLUTE_HOURS` | Maximum browser Session lifetime regardless of activity. |
| `SESSION_IDLE_MINUTES` | Browser Session expiry after inactivity. |
| `API_RATE_LIMIT_PER_MINUTE` | Per-Backend-process general API limit. |
| `LOGIN_RATE_LIMIT_PER_MINUTE` | Per-Backend-process login limit. |
| `NOTIFICATION_MODE` | `external` creates Reminder Outbox records for Hermes; `disabled` maintains events without reminder deliveries. |
| `SCHEDULER_HEARTBEAT_SECONDS` | Scheduler health heartbeat interval. |
| `REMINDER_SCAN_INTERVAL_MINUTES` | Interval between event/Outbox maintenance runs. |
| `REMINDER_SCAN_DAYS` | Future event window eligible for reminder maintenance. |
| `REMINDER_GRACE_DAYS` | Past-due window retained for restart catch-up. |
| `REMINDER_MAX_ATTEMPTS` | Failed delivery attempts before a Reminder Outbox item becomes dead. |
| `REMINDER_LEASE_SECONDS` | Exclusive Hermes claim duration; abandoned claims become eligible again after expiry. |

`COOKIE_SECURE=true` and the production environment are fixed in the production Compose definitions. Do not weaken them in production.

## User-managed reverse proxy

Point Nginx, Caddy, Traefik, Cloudflare Tunnel, Tailscale, or another proxy at `http://127.0.0.1:${SERVICE_PORT}` and terminate HTTPS there. Preserve `Host`, the client address, and `X-Forwarded-Proto=https`. Frontend uses the forwarded scheme to add HSTS.

The proxy must route both browser traffic and `/api/v1/*` to the same Frontend endpoint. Machine requests carrying `Authorization: Bearer ...` must reach the API without an interactive SSO redirect. If the proxy runs in Docker, add a user-owned Compose override/network or deliberately publish an address reachable by that proxy; the repository does not assume a proxy network name.

After proxy configuration, verify:

```bash
curl -fsS https://subscriptions.example.com/api/v1/health/ready
curl -fsS -H "Authorization: Bearer $TOKEN" https://subscriptions.example.com/api/v1/subscriptions
```

## Hermes integration and reminders

Create one API Token in Settings for routine Hermes interaction. Recommended scopes are:

```text
subscriptions:read subscriptions:write payments:write analytics:read audit:read reminders:consume
```

Set `HERMES_SUBSCRIPTION_API_URL=https://subscriptions.example.com` and `HERMES_SUBSCRIPTION_API_TOKEN` in Hermes secret configuration. Do not commit the Token. Install/use the repository's `hermes/` Skill and Tools for subscription lookup, editing, payments, reminder rules, and audit lookup.

The Skill does not run in the background. Configure exactly one recurring Hermes task to:

1. call `reminders_claim`;
2. deliver each returned message through Hermes' configured notification channel;
3. call `reminder_ack` after confirmed delivery, or `reminder_fail` with a concise error.

Claims are actor-owned and leased. Do not share a consumer Token among independent workers. Subscription Manager handles deduplication, retry scheduling, dead state, and restart catch-up; Hermes owns the final notification channel.

## systemd

Copy the repository to `/opt/subscription-manager`, protect `.env` with mode `0600`, and install the units from `deploy/systemd/` under `/etc/systemd/system/`. Then run:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now subscription-manager.service
sudo systemctl enable --now subscription-manager-backup.timer
systemctl list-timers subscription-manager-backup.timer
```

The timer runs daily at approximately 02:15 and retains seven days by default. Configure encrypted off-host replication separately and test a restore regularly using [BACKUP_RESTORE.md](BACKUP_RESTORE.md).

## Routine operations

- Health: `docker compose ... ps` and `/api/v1/health/live`, `/api/v1/health/ready` through Frontend.
- Logs: `docker compose ... logs --since 30m backend scheduler`; correlate failures with `request_id` and audit entries.
- Upgrade: create and verify a backup, fetch the reviewed revision, run `compose up -d --build`, and confirm migration, ready status, core UI, and Hermes API access.
- Rollback: do not downgrade application code across a migration without a verified compatible database backup. Restore into a new database and switch `DATABASE_URL` after validation.
- Password recovery: `docker compose ... exec backend python -m app.cli reset-admin-password --username <name>`.
- Token rotation: create the replacement with minimum scopes, update Hermes' secret, verify it, then revoke the old Token in Settings.
- Reminder failure: inspect Scheduler logs and Outbox audit/status, then verify the Hermes recurring task and Token scope. Keep Scheduler stopped during disaster recovery until data validation finishes.

Only one Scheduler instance may run. Do not scale the `scheduler` service. Backend may be scaled only after moving rate limiting to a shared gateway policy; the built-in limiter is per Backend process.
