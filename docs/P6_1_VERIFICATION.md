# P6.1 Hermes-first Production Refactor Verification

Date: 2026-07-19  
Implementation status: Complete  
Existing local-instance rollout: Deferred until a new verified backup can be created

## Reminder ownership boundary

- The ntfy adapter and all `NTFY_*` configuration were removed.
- Scheduler maintains billing/service events and, in `external` mode, durable Reminder Outbox records. `disabled` mode maintains events without creating deliveries.
- Scoped Hermes consumers use claim, ack, and fail endpoints. Claims record actor type/ID and a lease; wrong actors and expired leases cannot complete a delivery.
- Retry backoff, maximum attempts, dead state, grace-window expiry, deduplication, and restart reclamation remain owned by Subscription Manager.
- The Hermes Tool surface covers routine lookup, create/edit/status/archive/restore, payments, upcoming events, analytics, reminder-rule maintenance, Outbox consumption, and audit lookup. Risky writes require explicit confirmation.

## Deployment boundary

- Production Compose contains only PostgreSQL (when bundled), migration, Backend, Scheduler, and Frontend.
- `HERMES_DOMAIN`, `TRAEFIK_NETWORK`, and `TRAEFIK_CERT_RESOLVER` were removed. No proxy, DNS, or certificate provider is assumed.
- Only Frontend is published, defaulting to `127.0.0.1:8080`; Backend, Scheduler, and database have no host port mapping.
- Both bundled and external-database Compose files parse with their checked-in example environments.
- An isolated bundled production deployment completed migration and returned ready 200 through Frontend. Docker inspection showed null host bindings for Backend, Scheduler, and PostgreSQL.
- With `X-Forwarded-Proto: https`, the Frontend/API response included HSTS. Backend HTTPS access to the ECB rate source returned 200, proving the bridge network preserves required outbound access.
- The isolated validation project and volume were removed after the test.

## Configuration and naming

- New bundled databases and roles default to `subscription_manager`; the Compose project/systemd/service naming defaults to `subscription-manager`.
- Existing-volume behavior is explicitly documented: changing PostgreSQL initialization variables does not rename an existing database or role.
- Local development, bundled production, and external-database examples are separate. Every supported variable and its range/responsibility is described in `CONFIGURATION.md`.
- Backup filenames and new production systemd unit names use `subscription-manager`.

## Quality evidence

- Backend Ruff, Ruff format, and strict mypy (`app` and `tests`) passed.
- The PostgreSQL-backed suite passed 32/32 after the Outbox and lease-owner tests were added; Alembic reported no metadata drift.
- Hermes endpoint-mapping/confirmation/schema contract tests passed 3/3 without a database. The isolated real Hermes API/Tool verification also passed and removed its temporary stack.
- Frontend ESLint, TypeScript, 9/9 unit tests, and production PWA build passed.
- Development, bundled-production, and external-database Compose validation passed.

## Local rollout hold

The existing local project `hermes-subscription-manager-local` remains healthy and still uses its initialized PostgreSQL database/role name `hermes`. A pre-upgrade backup attempt was rejected by the host approval/usage layer before execution, so no container, volume, or database mutation was performed. In accordance with the upgrade runbook, rollout is intentionally paused until a hashed backup can be created; the old database/role names must be preserved in that deployment's environment during upgrade.
