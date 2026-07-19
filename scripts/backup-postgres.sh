#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROJECT_NAME="${PROJECT_NAME:-hermes-subscription-manager}"
OUTPUT_DIRECTORY="${OUTPUT_DIRECTORY:-$ROOT/backups}"
RETENTION_DAYS="${RETENTION_DAYS:-7}"
POSTGRES_DB="${POSTGRES_DB:-hermes}"
POSTGRES_USER="${POSTGRES_USER:-hermes}"

if [[ "$RETENTION_DAYS" -lt 1 ]]; then echo "RETENTION_DAYS must be at least 1" >&2; exit 2; fi
mkdir -p -- "$OUTPUT_DIRECTORY"
OUTPUT_DIRECTORY="$(cd "$OUTPUT_DIRECTORY" && pwd)"
if [[ "$OUTPUT_DIRECTORY" == "/" ]]; then echo "Refusing to use / as backup directory" >&2; exit 2; fi

timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
name="hermes-$timestamp.dump"
container_path="/tmp/$name"
output_path="$OUTPUT_DIRECTORY/$name"
cleanup() { docker compose -p "$PROJECT_NAME" exec -T db rm -f "$container_path" >/dev/null 2>&1 || true; }
trap cleanup EXIT

docker compose -p "$PROJECT_NAME" exec -T db pg_dump --format=custom --compress=9 --no-owner --no-privileges --username="$POSTGRES_USER" --dbname="$POSTGRES_DB" --file="$container_path"
docker compose -p "$PROJECT_NAME" cp "db:$container_path" "$output_path"
(cd "$OUTPUT_DIRECTORY" && sha256sum "$name" > "$name.sha256")

find "$OUTPUT_DIRECTORY" -maxdepth 1 -type f -name 'hermes-*.dump' -mtime "+$RETENTION_DAYS" -print0 |
  while IFS= read -r -d '' expired; do rm -f -- "$expired" "$expired.sha256"; done
printf '%s\n' "$output_path"
