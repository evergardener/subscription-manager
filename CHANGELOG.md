# Changelog

This file records user-visible changes and deployment-relevant maintenance for Hermes Subscription Manager. Dates use Asia/Shanghai calendar dates.

## 2026-07-23

### Added

- Added a gated GitHub Actions publishing job for Backend and Frontend GHCR images on `linux/amd64` and `linux/arm64`.
- Added immutable `sha-<full commit>`, moving `main`, moving `latest`, and SemVer image tags. `latest` updates only after every CI job succeeds on `main`.

### Fixed

- Archived subscriptions no longer contribute future billing events, Upcoming Events, forecast analytics, Dashboard renewal totals, or new and claimable reminder deliveries.
- Historical plans, payments, deliveries, and audit records remain available after archiving; restoring a subscription makes its relevant future schedule eligible again.
- Added `greenlet` as an explicit Backend dependency so SQLAlchemy async database operations work on Apple Silicon as well as the previously covered platforms.
- Updated the Frontend lockfile from vulnerable `fast-uri` 3.1.3 to 3.1.4.
- Updated the P0 architecture validator to recognize and verify all six current CI jobs.

### Changed

- Project documentation now records that the application is connected to Hermes and in real-world use.
- The P0 development-host handoff is explicitly marked as a historical snapshot.
- Added regression coverage for archived-subscription forecasts, event visibility, event generation, reminder generation, and reminder claiming.
- Production Compose and systemd now pull prebuilt GHCR images instead of compiling application source on the Hermes host.
- Backend CI and the P0 gate invoke pytest through the active Python interpreter, avoiding console-script import-path differences across development hosts.
- Production Compose and deployment documentation now explicitly identify both GHCR packages as public and require no registry credentials on the Hermes host.

### Validation

- Backend Ruff, format, and strict mypy checks passed.
- All 33 Backend tests passed with 84.64% domain/service coverage.
- Alembic reported no metadata drift; downgrade to base and upgrade to head passed against an isolated PostgreSQL database.
- Frontend audit reported zero vulnerabilities; lint, type-check, all 9 unit tests, and the production PWA build passed.
- The isolated Docker Compose stack rebuilt successfully, migrated to `b6d2c9e41a70`, returned 200 from Backend and Frontend health endpoints, and produced no blocking Backend, Scheduler, Frontend, or migration log errors.
- The GHCR workflow and both image-based production Compose variants passed static validation; the native Docker builds used by the workflow also passed the isolated full-stack smoke test.
- Anonymous manifest inspection succeeded for both `latest` images and confirmed `linux/amd64` and `linux/arm64` variants.

### Deployment notes

- No database migration was added.
- Both GHCR Packages are already Public; do not configure a GitHub PAT or GHCR login on the deployment host.
- Pull the new deployment revision, keep `IMAGE_TAG=latest` for automatic newest-successful deployment or pin the published `sha-*` tag, then run Compose `pull` and `up -d --wait`.
- Existing subscription and payment data require no manual conversion.

## Earlier milestones

P0 through P6.1 implementation and verification history predates this changelog. See the milestone records under [`docs/`](docs/) and the current status in [`README.md`](README.md).
