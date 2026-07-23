# Configuration Reference

Configuration is supplied through environment variables. Copy one example to `.env`, set secrets locally, and never commit the populated file:

- `.env.example`: local development Compose;
- `deploy/.env.production.example`: bundled PostgreSQL production;
- `deploy/.env.external-db.example`: external PostgreSQL production.

## Application and database

| Variable | Default/profile | Meaning |
| --- | --- | --- |
| `APP_NAME` | `Hermes Subscription Manager` | API metadata name. This is not a domain, Compose project name, or database name. |
| `ENVIRONMENT` | `development`; production Compose fixes `production` | Enables environment safety checks. Production requires secure cookies. |
| `LOG_LEVEL` | `INFO` | Python logging threshold. |
| `DATABASE_URL` | Built by bundled Compose | SQLAlchemy URL used by Backend, Scheduler, migration, and local Python commands. Required explicitly for external PostgreSQL. |
| `POSTGRES_DB` | `subscription_manager` | Database initialized by the bundled PostgreSQL image. It does not rename an existing database. |
| `POSTGRES_USER` | `subscription_manager` | Role initialized by the bundled PostgreSQL image. It does not rename an existing role. |
| `POSTGRES_PASSWORD` | no usable default | Bundled database password. Use a URL-safe random value because Compose embeds it in `DATABASE_URL`. |

The project remains a Hermes component, but generic infrastructure identifiers use `subscription-manager`/`subscription_manager` to avoid implying that the database or deployment represents all of Hermes. Python/npm package names retain their historical internal names because changing them has no deployment effect.

## Container images

| Variable | Default/profile | Meaning |
| --- | --- | --- |
| `IMAGE_TAG` | `latest`, production | Tag applied to both `ghcr.io/evergardener/subscription-manager-backend` and `ghcr.io/evergardener/subscription-manager-frontend`. `latest` and `main` follow the newest successful main-branch CI build; `sha-<40-character-commit>` is immutable and preferred for reproducible releases and rollback. |

Production Compose pulls `linux/amd64` or `linux/arm64` images from GHCR and does
not build application source. Local `compose.yml` remains build-based for
development. Both GHCR packages are public; no registry credential is required
on production hosts.

## Published endpoints and browser security

| Variable | Default/profile | Meaning |
| --- | --- | --- |
| `BACKEND_PORT` | `8000`, development only | Direct host port for Backend during local development. Production does not publish Backend. |
| `FRONTEND_PORT` | `8080`, development only | Local development Frontend port. |
| `SERVICE_BIND_ADDRESS` | `127.0.0.1`, production | Address on which production Frontend is published for a user-managed reverse proxy. |
| `SERVICE_PORT` | `8080`, production | Production Frontend host port. |
| `COOKIE_SECURE` | `false`, development; production Compose fixes `true` | Allows Session cookies only over HTTPS when true. Do not override production. |
| `SESSION_ABSOLUTE_HOURS` | `168` | Hard maximum browser Session age. Range: 1–720 hours. |
| `SESSION_IDLE_MINUTES` | `60` | Browser Session inactivity timeout. Range: 5–1440 minutes. |
| `API_RATE_LIMIT_PER_MINUTE` | `300` | General request limit per direct client per Backend process. |
| `LOGIN_RATE_LIMIT_PER_MINUTE` | `10` | Login attempt limit per direct client per Backend process. |

## Scheduler and Reminder Outbox

| Variable | Default | Meaning |
| --- | --- | --- |
| `NOTIFICATION_MODE` | `external` | `external` creates Reminder Outbox records for Hermes; `disabled` only maintains billing/service events. |
| `SCHEDULER_HEARTBEAT_SECONDS` | `60` | Interval at which the Scheduler refreshes its health heartbeat. Range: 5–3600 seconds. |
| `REMINDER_SCAN_INTERVAL_MINUTES` | `5` | Event and Outbox maintenance interval. Range: 1–1440 minutes. |
| `REMINDER_SCAN_DAYS` | `30` | Future horizon considered during reminder maintenance. Range: 1–366 days. |
| `REMINDER_GRACE_DAYS` | `3` | Restart catch-up window for missed reminders. Range: 0–30 days. |
| `REMINDER_MAX_ATTEMPTS` | `5` | Failed Hermes deliveries allowed before dead state. Range: 1–20. |
| `REMINDER_LEASE_SECONDS` | `120` | Actor-owned claim lease before an abandoned item can be reclaimed. Range: 30–3600 seconds. |

`NOTIFICATION_MODE` does not send messages. Exactly one recurring Hermes consumer must claim due items, send through Hermes, and call ack/fail. `NTFY_*`, `HERMES_DOMAIN`, `TRAEFIK_NETWORK`, and `TRAEFIK_CERT_RESOLVER` were removed; they are not accepted deployment settings.

## Hermes client

These variables belong in Hermes' protected runtime configuration, not in Subscription Manager's production `.env` unless both processes intentionally share a secret store:

| Variable | Meaning |
| --- | --- |
| `HERMES_SUBSCRIPTION_API_URL` | Public HTTPS base URL routed to Subscription Manager Frontend, without `/api/v1`. |
| `HERMES_SUBSCRIPTION_API_TOKEN` | One-time-revealed scoped Token. Recommended scopes: `subscriptions:read`, `subscriptions:write`, `payments:write`, `analytics:read`, `audit:read`, `reminders:consume`. |

## Existing-volume migration rule

The PostgreSQL image applies `POSTGRES_DB`, `POSTGRES_USER`, and `POSTGRES_PASSWORD` only when initializing an empty data directory. When upgrading an existing deployment, first inspect and preserve the database/role names that its volume already uses. Renaming either is a separate database migration involving roles, ownership, connection URLs, backup, and rollback; it must not be attempted by merely editing `.env`.
