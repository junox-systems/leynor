#!/bin/bash
# Boot the prod image like docker-stack.yml (db + web + qcluster) and probe it.
# Usage: prod/smoke.sh [image]   (default: leynor)
set -euo pipefail

IMAGE="${1:-${APP_SLUG:-leynor}}"
P="smoke-$$"
ENV=(
  -e DATABASE_URL="postgres://${APP_SLUG:-leynor}:smoke@$P-db:5432/${APP_SLUG:-leynor}"
  -e SECRET_KEY="smoke-$(od -An -N16 -tx1 /dev/urandom | tr -d ' \n')"
  -e DEFAULT_FROM_EMAIL=smoke@example.com
  -e CSRF_TRUSTED_ORIGINS=https://example.com
  -e ALLOWED_HOSTS=localhost
  -e APP_ARTIFACT_ENDPOINT_URL="http://$P-s3:8333"
  -e APP_ARTIFACT_ACCESS_KEY=smoke
  -e APP_ARTIFACT_SECRET_KEY="smoke-secret"
)

cleanup() { docker rm -f "$P-web" "$P-q" "$P-db" "$P-s3" >/dev/null 2>&1 || true; docker network rm "$P" >/dev/null 2>&1 || true; }
fail() {
  echo "FAIL: $*"
  for c in web q s3; do echo "--- $c logs ---"; docker logs "$P-$c" 2>&1 | tail -30 || true; done
  exit 1
}
trap cleanup EXIT

docker network create "$P" >/dev/null
docker run -d --name "$P-db" --network "$P" -e POSTGRES_USER=${APP_SLUG:-leynor} -e POSTGRES_PASSWORD=smoke -e POSTGRES_DB=${APP_SLUG:-leynor} paradedb/paradedb:0.26.2-pg18 >/dev/null
docker run -d --name "$P-s3" --network "$P" -e AWS_ACCESS_KEY_ID=smoke -e AWS_SECRET_ACCESS_KEY=smoke-secret chrislusf/seaweedfs:4.52 server -s3 -dir=/data >/dev/null
# Production startup only checks the bucket; here, like a provisioned bucket, it exists first.
docker run --rm --network "$P" "${ENV[@]}" --entrypoint python "$IMAGE" manage.py artifact_bucket --create \
  || fail "could not create the artifacts bucket"
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

# Private app: "/" only redirects to sign-in, so the stylesheet link lives on
# that page. pipefail turns grep's no-match into a silent exit without `|| true`.
code=$(get /)
[ "$code" = 302 ] || fail "/ returned $code, expected the login redirect"

css=$(docker exec "$P-web" curl -sS -H "Host: localhost" http://127.0.0.1:8000/accounts/login/ \
  | grep -o '/static/[^"]*\.css' | head -1 || true)
[ -n "$css" ] || fail "no stylesheet linked from /accounts/login/"

for path in /accounts/login/ /docs/openapi.json "$css"; do
  code=$(get "$path")
  echo "$code $path"
  [ "$code" = 200 ] || fail "$path returned $code"
done

for _ in $(seq 30); do docker logs "$P-q" 2>&1 | grep -q "Q Cluster .* running" && break; sleep 2; done
docker logs "$P-q" 2>&1 | grep -q "Q Cluster .* running" || fail "qcluster did not start"
echo "200 qcluster running"

# Reel artifacts: what one process writes, another reads (web -> worker).
key="smoke/$P.txt"
docker exec "$P-web" python manage.py shell -c "from apps.runs.artifacts import ArtifactStore; ArtifactStore().put('$key', 'smoke-bytes')" >/dev/null 2>&1 \
  || fail "web could not write an artifact"
got=$(docker exec "$P-q" python manage.py shell -c "from apps.runs.artifacts import ArtifactStore; print(ArtifactStore().get('$key').decode())" 2>/dev/null | tail -1)
[ "$got" = smoke-bytes ] || fail "qcluster read '$got' from the artifact store, expected smoke-bytes"
echo "200 artifacts shared between web and qcluster"

echo "OK: $IMAGE"
