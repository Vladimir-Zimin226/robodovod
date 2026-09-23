#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
ENV_FILE=${ENV_FILE:-$ROOT/.env.production}
BACKUP_DIR=${BACKUP_DIR:-/var/backups/robodovod}
DOCKER=${DOCKER:-docker}
COMPOSE="$DOCKER compose --env-file $ENV_FILE -f $ROOT/compose.yaml -f $ROOT/compose.production.yaml"

test -f "$ENV_FILE" || { echo "production env file is missing" >&2; exit 2; }
DB_NAME=$(sed -n 's/^POSTGRES_DB=//p' "$ENV_FILE" | tail -n 1)
case "$DB_NAME" in ''|*[!A-Za-z0-9_]*) echo "POSTGRES_DB must be a safe identifier" >&2; exit 2;; esac

umask 077
mkdir -p "$BACKUP_DIR"
STAMP=$(date -u +%Y%m%dT%H%M%SZ)
DB_DUMP="$BACKUP_DIR/postgres-$STAMP.dump"
UPLOADS="$BACKUP_DIR/uploads-$STAMP.tar.gz"

$COMPOSE exec -T --user postgres db pg_dump --format=custom --dbname "$DB_NAME" > "$DB_DUMP.tmp"
test -s "$DB_DUMP.tmp"
mv "$DB_DUMP.tmp" "$DB_DUMP"

PROJECT=$(sed -n 's/^COMPOSE_PROJECT_NAME=//p' "$ENV_FILE" | tail -n 1)
case "$PROJECT" in ''|*[!A-Za-z0-9_-]*) echo "COMPOSE_PROJECT_NAME is invalid" >&2; exit 2;; esac
$DOCKER run --rm \
  --volume "${PROJECT}_project_uploads:/source:ro" \
  --volume "$BACKUP_DIR:/backup" \
  alpine:3.22.2 sh -c "tar -C /source -czf /backup/$(basename "$UPLOADS") ."

sha256sum "$DB_DUMP" "$UPLOADS" > "$BACKUP_DIR/sha256-$STAMP.txt"
chmod 600 "$DB_DUMP" "$UPLOADS" "$BACKUP_DIR/sha256-$STAMP.txt"
printf '%s\n' "$DB_DUMP" "$UPLOADS" "$BACKUP_DIR/sha256-$STAMP.txt"
