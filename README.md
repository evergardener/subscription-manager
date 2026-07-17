# Hermes Subscription Manager

Self-hosted subscription and digital-service lifecycle manager. This repository is being implemented from the approved v1.1 development specification.

## P0 status

P0 establishes the architecture and delivery pipeline only. It intentionally contains no subscription business tables or P1 domain behavior.

Included:

- FastAPI backend with JSON logs, request IDs, OpenAPI, and live/ready health checks.
- Independent APScheduler process using the same backend image.
- React/TypeScript/Vite frontend with a typed health probe.
- Empty Alembic baseline; no ORM auto-create path.
- Docker Compose services for PostgreSQL, migration, backend, scheduler, and frontend.
- Backend and frontend lint, type-check, test, build, migration, and Compose CI jobs.

## Repository layout

```text
subscription-manager/
├─ backend/               FastAPI, scheduler, Alembic, tests
├─ frontend/              React/Vite application and tests
├─ docs/                  approved specification and implementation plan
├─ scripts/verify-p0.ps1  local P0 verification
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

## Local backend

```powershell
cd backend
uv sync --frozen
$env:DATABASE_URL = 'postgresql+psycopg://hermes:password@localhost:5432/hermes'
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --log-config logging.json
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
- P1 will implement Session, CSRF, scoped API Token, domain tables, audit transactions, and lifecycle rules. They are deliberately absent from P0.

## Authoritative documents

- [Development specification](docs/Hermes_Subscription_Manager_Development_Spec.md)
- [Implementation plan](docs/Hermes_Subscription_Manager_Implementation_Plan.md)
- [P0 verification record](docs/P0_VERIFICATION.md)
- [Development host migration handoff](docs/DEVELOPMENT_HOST_HANDOFF.md)

Any behavior that deviates from the approved specification must update the Markdown decision record before code changes are accepted.
