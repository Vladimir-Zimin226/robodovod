#!/bin/sh
set -eu

test "$#" -eq 1 || { echo "usage: restore-drill.sh /path/to/postgres.dump" >&2; exit 2; }
DUMP=$1
test -s "$DUMP" || { echo "backup dump is missing or empty" >&2; exit 2; }

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/../.." && pwd)
ENV_FILE=${ENV_FILE:-$ROOT/.env.production}
DOCKER=${DOCKER:-docker}
COMPOSE="$DOCKER compose --env-file $ENV_FILE -f $ROOT/compose.yaml -f $ROOT/compose.production.yaml"
DRILL_DB="robodovod_restore_$(date -u +%Y%m%d%H%M%S)"

cleanup() {
  $COMPOSE exec -T --user postgres db dropdb --if-exists "$DRILL_DB" >/dev/null 2>&1 || true
}
trap cleanup EXIT INT TERM

$COMPOSE exec -T --user postgres db createdb "$DRILL_DB"
$COMPOSE exec -T --user postgres db pg_restore --exit-on-error --dbname "$DRILL_DB" < "$DUMP"
REVISION=$($COMPOSE exec -T --user postgres db psql --dbname "$DRILL_DB" --tuples-only --no-align --command "SELECT version_num FROM alembic_version")
TABLES=$($COMPOSE exec -T --user postgres db psql --dbname "$DRILL_DB" --tuples-only --no-align --command "SELECT count(*) FROM information_schema.tables WHERE table_schema='public'")
test -n "$REVISION"
test "$TABLES" -ge 31
printf 'restore drill ok: revision=%s tables=%s\n' "$REVISION" "$TABLES"
