#!/bin/bash
# Boot the prod image like docker-stack.yml (db + web + qcluster) and probe it.
# Usage: prod/smoke.sh [image]   (default: django-starter-kit)
set -euo pipefail

IMAGE="${1:-django-starter-kit}"
P="smoke-$$"
ENV=(
  -e DATABASE_URL="postgres://django:smoke@$P-db:5432/django"
  -e SECRET_KEY="smoke-$(od -An -N16 -tx1 /dev/urandom | tr -d ' \n')"
  -e DEFAULT_FROM_EMAIL=smoke@example.com
  -e CSRF_TRUSTED_ORIGINS=https://example.com
  -e ALLOWED_HOSTS=localhost
)

cleanup() { docker rm -f "$P-web" "$P-q" "$P-db" >/dev/null 2>&1 || true; docker network rm "$P" >/dev/null 2>&1 || true; }
fail() {
  echo "FAIL: $*"
  for c in web q; do echo "--- $c logs ---"; docker logs "$P-$c" 2>&1 | tail -30 || true; done
  exit 1
}
trap cleanup EXIT

docker network create "$P" >/dev/null
docker run -d --name "$P-db" --network "$P" -e POSTGRES_USER=django -e POSTGRES_PASSWORD=smoke -e POSTGRES_DB=django paradedb/paradedb:0.26.2-pg18 >/dev/null
docker run -d --name "$P-web" --network "$P" "${ENV[@]}" "$IMAGE" >/dev/null
docker run -d --name "$P-q" --network "$P" "${ENV[@]}" "$IMAGE" python manage.py qcluster >/dev/null

get() { docker exec "$P-web" curl -sS -o /dev/null -w '%{http_code}' -H "Host: localhost" "http://127.0.0.1:8000$1" 2>/dev/null || true; }

echo "Waiting for /healthz/ ..."
for _ in $(seq 60); do
  [ "$(get /healthz/)" = 200 ] && break
  for c in web q; do [ "$(docker inspect -f '{{.State.Running}}' "$P-$c")" = true ] || fail "$c container exited"; done
  sleep 2
done
[ "$(get /healthz/)" = 200 ] || fail "/healthz/ never returned 200"

css=$(docker exec "$P-web" curl -sS -H "Host: localhost" http://127.0.0.1:8000/ | grep -o '/static/[^"]*\.css' | head -1)
[ -n "$css" ] || fail "no stylesheet linked from /"

for path in / /accounts/login/ /docs/openapi.json "$css"; do
  code=$(get "$path")
  echo "$code $path"
  [ "$code" = 200 ] || fail "$path returned $code"
done

for _ in $(seq 30); do docker logs "$P-q" 2>&1 | grep -q "Q Cluster .* running" && break; sleep 2; done
docker logs "$P-q" 2>&1 | grep -q "Q Cluster .* running" || fail "qcluster did not start"
echo "200 qcluster running"

echo "OK: $IMAGE"
