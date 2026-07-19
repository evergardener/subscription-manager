#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "Usage: $0 BACKUP_PATH" >&2
  exit 2
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKUP_PATH="$(realpath "$1")"
PROJECT_NAME="${PROJECT_NAME:-subscription-manager-restore-validation}"
SKIP_BUILD="${SKIP_BUILD:-false}"

if [[ "$PROJECT_NAME" != *restore-validation ]]; then
  echo "PROJECT_NAME must end in restore-validation" >&2
  exit 2
fi
if [[ ! -f "$BACKUP_PATH" || ! -f "$BACKUP_PATH.sha256" ]]; then
  echo "The backup and its .sha256 sidecar are required" >&2
  exit 2
fi

if [[ -n "$(docker ps -aq --filter "label=com.docker.compose.project=$PROJECT_NAME")" ]] ||
   [[ -n "$(docker volume ls -q --filter "label=com.docker.compose.project=$PROJECT_NAME")" ]] ||
   [[ -n "$(docker network ls -q --filter "label=com.docker.compose.project=$PROJECT_NAME")" ]]; then
  echo "Refusing to reuse existing Docker resources for $PROJECT_NAME" >&2
  exit 2
fi

backup_directory="$(dirname "$BACKUP_PATH")"
backup_name="$(basename "$BACKUP_PATH")"
(cd "$backup_directory" && sha256sum --check "$backup_name.sha256")

export POSTGRES_PASSWORD="restore-validation-only"
export POSTGRES_DB="subscription_manager_restore_validation"
export POSTGRES_USER="subscription_manager"
export BACKEND_PORT="18200"
export FRONTEND_PORT="18280"
container_path="/tmp/subscription-manager-restore-validation.dump"
created=false

cleanup() {
  if [[ "$created" == true ]]; then
    docker compose -p "$PROJECT_NAME" down --volumes --remove-orphans >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

cd "$ROOT"
created=true
docker compose -p "$PROJECT_NAME" up -d db

for _ in {1..60}; do
  if docker compose -p "$PROJECT_NAME" exec -T db \
      pg_isready --username="$POSTGRES_USER" --dbname="$POSTGRES_DB" >/dev/null 2>&1; then
    break
  fi
  sleep 2
done
docker compose -p "$PROJECT_NAME" exec -T db \
  pg_isready --username="$POSTGRES_USER" --dbname="$POSTGRES_DB" >/dev/null

docker compose -p "$PROJECT_NAME" cp "$BACKUP_PATH" "db:$container_path"
docker compose -p "$PROJECT_NAME" exec -T db pg_restore \
  --exit-on-error --no-owner --no-privileges \
  --username="$POSTGRES_USER" --dbname="$POSTGRES_DB" "$container_path"

build_arguments=()
if [[ "$SKIP_BUILD" != true ]]; then build_arguments+=(--build); fi
docker compose -p "$PROJECT_NAME" up -d "${build_arguments[@]}" backend

ready=false
for _ in {1..90}; do
  if curl --fail --silent --show-error \
      "http://127.0.0.1:$BACKEND_PORT/api/v1/health/ready" >/dev/null 2>&1; then
    ready=true
    break
  fi
  sleep 2
done
if [[ "$ready" != true ]]; then
  echo "Restored Backend did not become ready" >&2
  exit 1
fi

required_tables=(users subscriptions billing_plans billing_events payments audit_logs alembic_version)
for table in "${required_tables[@]}"; do
  exists="$(docker compose -p "$PROJECT_NAME" exec -T db psql \
    --username="$POSTGRES_USER" --dbname="$POSTGRES_DB" --tuples-only --no-align \
    --command="SELECT to_regclass('public.$table') IS NOT NULL" | tr -d '[:space:]')"
  if [[ "$exists" != t ]]; then
    echo "Required table $table is missing after restore" >&2
    exit 1
  fi
done

version="$(docker compose -p "$PROJECT_NAME" exec -T db psql \
  --username="$POSTGRES_USER" --dbname="$POSTGRES_DB" --tuples-only --no-align \
  --command='SELECT version_num FROM alembic_version' | tr -d '[:space:]')"
subscriptions="$(docker compose -p "$PROJECT_NAME" exec -T db psql \
  --username="$POSTGRES_USER" --dbname="$POSTGRES_DB" --tuples-only --no-align \
  --command='SELECT count(*) FROM subscriptions' | tr -d '[:space:]')"
if [[ -z "$version" || ! "$subscriptions" =~ ^[0-9]+$ ]]; then
  echo "Migration or subscription verification failed" >&2
  exit 1
fi

echo "Restore verification passed: migration=$version subscriptions=$subscriptions"
