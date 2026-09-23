#!/bin/sh
set -eu

BASE_URL=${BASE_URL:-https://robodovod.ru}
curl --fail --silent --show-error "$BASE_URL/health" | grep -F '"status":"ok"' >/dev/null
curl --fail --silent --show-error "$BASE_URL/ready" | grep -F '"status":"ready"' >/dev/null
curl --fail --silent --show-error --head "$BASE_URL/" >/dev/null
curl --fail --silent --show-error --head "https://www.robodovod.ru/" | grep -Ei '^location: https://robodovod.ru/' >/dev/null
printf 'public smoke ok: %s\n' "$BASE_URL"
