# Hermes Subscription Manager

Self-hosted subscription and digital-service lifecycle manager implemented from the approved v1.1 development specification.

将仓库交给 Hermes 所在主机部署和安装时，从 [Hermes 主机部署交接入口](HERMES_DEPLOYMENT_HANDOFF.md) 开始。生产主机直接拉取 GitHub Actions 构建的 GHCR 镜像，无需在 Hermes 主机编译应用。部署完成后的日常操作见 [用户使用说明](docs/USER_GUIDE.md)。

## Current status

P0 through P6.1 are implemented, and the application is connected to Hermes for real-world use. The backend provides the domain schema, authentication, core subscription APIs, persistent billing events, payments, audit logs, reminder rules, and a reliable Reminder Outbox. The frontend is an authenticated responsive PWA with the complete management workflow and offline read-only behavior. Hermes performs routine read/write operations and consumes due reminders through scoped Tools.

Archived subscriptions retain their plans, payments, and audit history for restoration and review, but are excluded from future billing-event maintenance, upcoming-event queries, forecast analytics, Dashboard renewal totals, and reminder delivery.

Included:

- FastAPI backend with JSON logs, request IDs, OpenAPI, and live/ready health checks.
- Independent APScheduler process using the same backend image.
- React/TypeScript/Vite PWA with Dashboard, subscriptions, events, analytics, settings, and API Token management.
- Alembic-managed P1 schema; no ORM auto-create path.
- Docker Compose services for PostgreSQL, migration, backend, scheduler, and frontend.
- Session/CSRF for the Web UI and scoped API Tokens for Hermes, scheduler, and automation clients.
- Backend and frontend lint, type-check, test, coverage, build, migration, and Compose CI jobs.
- Multi-platform Backend and Frontend images published to GHCR only after the complete CI gate succeeds.

## Repository layout

```text
subscription-manager/
├─ backend/               FastAPI, scheduler, Alembic, tests
├─ frontend/              React/Vite application and tests
├─ docs/                  approved specification and implementation plan
├─ scripts/              local milestone verification gates
├─ compose.yml
└─ .github/workflows/ci.yml
```

## Prerequisites

- Docker Engine with Compose v2 for the supported full-stack path.
- Python 3.12 and `uv` for local backend development.
- Node.js 22 and npm for local frontend development.

## Local full-stack startup

1. Copy `.env.example` to `.env`.
2. Replace `POSTGRES_PASSWORD`. Keep `NOTIFICATION_MODE=external` when Hermes will deliver reminders, or use `disabled` when only event maintenance is required. Do not commit `.env`.
3. Run:

```powershell
docker compose up --build
```

Compose runs the explicit `migrate` job before starting backend and scheduler. The application never calls `create_all()`.

Endpoints:

- Frontend: <http://localhost:8080>
- Backend OpenAPI: <http://localhost:8000/docs>
- Live: <http://localhost:8000/api/v1/health/live>
- Ready: <http://localhost:8000/api/v1/health/ready>

Stop the stack with `docker compose down`. Add `--volumes` only when intentionally deleting the local PostgreSQL data volume.

Production Compose pulls these images instead of building source on the server:

- `ghcr.io/evergardener/subscription-manager-backend`
- `ghcr.io/evergardener/subscription-manager-frontend`

`IMAGE_TAG=latest` follows the newest successful `main` build. Pin
`IMAGE_TAG=sha-<40-character-commit>` for reproducible deployment and rollback.
The images support `linux/amd64` and `linux/arm64`.

On a new empty database, create the single local administrator once:

```powershell
Invoke-RestMethod -Method Post http://localhost:8000/api/v1/auth/bootstrap `
  -ContentType application/json `
  -Body '{"username":"admin","password":"replace-with-at-least-12-characters"}'
```

The bootstrap endpoint returns HTTP 409 after an administrator exists. Login through `POST /api/v1/auth/login`; state-changing Session requests must send the returned CSRF token as `X-CSRF-Token`.

An authenticated administrator can change the password from **Settings → Current session → 修改密码**. A successful change revokes every existing browser Session. If the password is forgotten, run the interactive reset locally on the server:

```powershell
docker compose exec backend python -m app.cli reset-admin-password --username admin
```

The command prompts twice without echoing the password, revokes all Sessions, and writes a password-reset audit entry without storing the password or hash in audit data. It requires direct access to the application host; there is intentionally no email or security-question recovery flow.

## Local backend

```powershell
cd backend
uv sync --frozen
$env:DATABASE_URL = 'postgresql+psycopg://subscription_manager:password@localhost:5432/subscription_manager'
uv run alembic upgrade head
uv run python -m app.server
```

Run the scheduler separately:

```powershell
cd backend
uv run python -m app.scheduler
```

## Local frontend

```powershell
cd frontend
npm ci
npm run dev
```

Vite proxies `/api` to `http://localhost:8000`.

## Verification

The complete local P0 gate is:

```powershell
./scripts/verify-p0.ps1
```

It runs Backend Ruff/format/mypy/pytest/Alembic offline generation, Frontend lint/typecheck/test/build, and `docker compose config`. `-SkipCompose` is only a partial check for machines without Docker and does not prove the full P0 gate.

For the P1–P3 gate, point `TEST_DATABASE_URL` at a disposable PostgreSQL database whose name ends in `test` or `validation`, then run:

```powershell
./scripts/verify-p3.ps1
```

This additionally enforces 80% domain/service coverage, checks Alembic metadata drift, and performs a destructive downgrade/upgrade cycle only against the explicitly named disposable test database.

For P4 and later UI changes, run the isolated browser acceptance gate:

```powershell
./scripts/verify-e2e.ps1
```

It starts a separate Compose project on ports 18000/18080 with a fresh disposable database, exercises the authenticated workflow on desktop and at 360 px, then removes only that project's containers and volume. This avoids false results from an existing administrator or retained application data. See [P4 verification record](docs/P4_VERIFICATION.md) for the full evidence and prerequisites.

For the P5 Hermes API and actor boundary, run:

```powershell
./scripts/verify-hermes.ps1 -PythonPath ./backend/.venv/Scripts/python.exe
```

The Hermes Skill is in `hermes/`. Runtime configuration uses `HERMES_SUBSCRIPTION_API_URL` and `HERMES_SUBSCRIPTION_API_TOKEN`; never commit the token. See [P5 verification record](docs/P5_VERIFICATION.md).

For the destructive-safety-scoped backup/restore gate, run:

```powershell
./scripts/verify-backup-restore.ps1
```

Production backup and disaster-recovery steps are in the [backup and restore runbook](docs/BACKUP_RESTORE.md). A dump is not considered valid until the empty-database verifier passes.

Production reverse-proxy integration, systemd, bundled/external PostgreSQL, upgrades, rollback, logging, Token rotation, and Hermes reminder consumption are covered by the [operations runbook](docs/OPERATIONS.md).

Every supported environment variable, its scope, default, and existing-volume behavior is documented in the [configuration reference](docs/CONFIGURATION.md).

Run the isolated 10,000-subscription P95 gate with:

```powershell
./scripts/verify-performance.ps1 -PythonPath ./backend/.venv/Scripts/python.exe
```

## Development workflow

- Use the Docker Linux Engine installed on the active development host for integration and runtime validation.
- Keep changes and generated project state inside this repository.
- Complete the checks relevant to each coherent change before committing it.
- Automatically create one descriptive Git commit for every validated change; do not push unless explicitly requested.
- Follow the persistent repository instructions in [AGENTS.md](AGENTS.md).

## Configuration and security

- Configuration comes from environment variables; `.env.example` contains placeholders only.
- Logs are structured JSON and include `request_id`, `actor`, and `entity_id` fields.
- User-supplied `X-Request-ID` is accepted only when non-empty and at most 100 characters.
- API traffic defaults to 300 requests/minute per direct client and login attempts to 10/minute. Configure `API_RATE_LIMIT_PER_MINUTE` and `LOGIN_RATE_LIMIT_PER_MINUTE` for the deployment; HTTP 429 responses include `Retry-After`.
- Backend and frontend responses set CSP, anti-framing, MIME sniffing, referrer, and browser permissions controls. HTTPS proxy requests also receive HSTS.
- `NOTIFICATION_MODE=external` creates durable due-reminder Outbox records for Hermes to claim, deliver, and acknowledge. `disabled` keeps billing/service events current but does not create reminder deliveries. Subscription Manager intentionally contains no ntfy or provider-specific delivery integration.
- The included Skill is an API capability description, not a background daemon. Production reminders require exactly one recurring Hermes task using a Token with `reminders:consume` scope. See [Hermes-first architecture](docs/HERMES_FIRST_ARCHITECTURE.md).
- The Dashboard retrieves the European Central Bank's latest working-day reference rates through the backend and caches them for six hours. Outbound HTTPS to `www.ecb.europa.eu` is required for the optional CNY estimate; original-currency totals remain available when it is unreachable.

## Authoritative documents

- [Changelog](CHANGELOG.md)
- [Development specification](docs/Hermes_Subscription_Manager_Development_Spec.md)
- [Implementation plan](docs/Hermes_Subscription_Manager_Implementation_Plan.md)
- [P0 verification record](docs/P0_VERIFICATION.md)
- [P3 verification record](docs/P3_VERIFICATION.md)
- [P4 verification record](docs/P4_VERIFICATION.md)
- [P5 verification record](docs/P5_VERIFICATION.md)
- [P6 verification record](docs/P6_VERIFICATION.md)
- [P6.1 Hermes-first verification record](docs/P6_1_VERIFICATION.md)
- [Configuration reference](docs/CONFIGURATION.md)
- [Hermes-first architecture](docs/HERMES_FIRST_ARCHITECTURE.md)
- [Hermes host deployment guide](docs/HERMES_HOST_DEPLOYMENT.md)
- [User guide](docs/USER_GUIDE.md)
- [Development host migration handoff](docs/DEVELOPMENT_HOST_HANDOFF.md)

Any behavior that deviates from the approved specification must update the Markdown decision record before code changes are accepted.
