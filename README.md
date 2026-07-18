# Hermes Subscription Manager

Self-hosted subscription and digital-service lifecycle manager. This repository is being implemented from the approved v1.1 development specification.

## Current status

P0 through P4 are implemented. The backend provides the domain schema, authentication, core subscription APIs, persistent billing events, payments, audit logs, reminder rules, and the independent ntfy-capable scheduler. The frontend is now an authenticated responsive PWA with the complete MVP management workflow and offline read-only behavior.

Included:

- FastAPI backend with JSON logs, request IDs, OpenAPI, and live/ready health checks.
- Independent APScheduler process using the same backend image.
- React/TypeScript/Vite PWA with Dashboard, subscriptions, events, analytics, settings, and API Token management.
- Alembic-managed P1 schema; no ORM auto-create path.
- Docker Compose services for PostgreSQL, migration, backend, scheduler, and frontend.
- Session/CSRF for the Web UI and scoped API Tokens for Hermes, scheduler, and automation clients.
- Backend and frontend lint, type-check, test, coverage, build, migration, and Compose CI jobs.

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

## Full-stack startup

1. Copy `.env.example` to `.env`.
2. Replace `POSTGRES_PASSWORD` and the ntfy placeholder values. Do not commit `.env`.
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

On a new empty database, create the single local administrator once:

```powershell
Invoke-RestMethod -Method Post http://localhost:8000/api/v1/auth/bootstrap `
  -ContentType application/json `
  -Body '{"username":"admin","password":"replace-with-at-least-12-characters"}'
```

The bootstrap endpoint returns HTTP 409 after an administrator exists. Login through `POST /api/v1/auth/login`; state-changing Session requests must send the returned CSRF token as `X-CSRF-Token`.

## Local backend

```powershell
cd backend
uv sync --frozen
$env:DATABASE_URL = 'postgresql+psycopg://hermes:password@localhost:5432/hermes'
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

For P4, start the full Compose stack and additionally run the browser acceptance suite:

```powershell
cd frontend
npm run test:e2e
```

It exercises the authenticated workflow on desktop and at 360 px, including offline read-only mode. See [P4 verification record](docs/P4_VERIFICATION.md) for the full evidence and prerequisites.

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
- Configure `NTFY_BASE_URL` and replace `NTFY_TOPIC=replace-me` before enabling real notification delivery. With the placeholder topic, scheduler scanning is explicitly skipped and logged.

## Authoritative documents

- [Development specification](docs/Hermes_Subscription_Manager_Development_Spec.md)
- [Implementation plan](docs/Hermes_Subscription_Manager_Implementation_Plan.md)
- [P0 verification record](docs/P0_VERIFICATION.md)
- [P3 verification record](docs/P3_VERIFICATION.md)
- [P4 verification record](docs/P4_VERIFICATION.md)
- [Development host migration handoff](docs/DEVELOPMENT_HOST_HANDOFF.md)

Any behavior that deviates from the approved specification must update the Markdown decision record before code changes are accepted.
