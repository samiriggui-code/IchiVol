#!/bin/bash
set -euo pipefail
cd /opt/ichivol

JEV_KEY="${1:-}"
if [ -z "$JEV_KEY" ]; then
  echo "usage: $0 <JEV_API_KEY>"
  exit 1
fi

echo "=== networks before ==="
docker inspect jevos-v4 --format '{{range $k,$v := .NetworkSettings.Networks}}{{$k}} {{$v.IPAddress}}{{println}}{{end}}'
docker inspect ichivol-engine --format '{{range $k,$v := .NetworkSettings.Networks}}{{$k}} {{$v.IPAddress}}{{println}}{{end}}'

# Attach jevos to ichivol network if missing
if ! docker inspect jevos-v4 --format '{{json .NetworkSettings.Networks}}' | grep -q '"ichivol"'; then
  echo "=== connect jevos-v4 to ichivol network ==="
  docker network connect ichivol jevos-v4 || true
fi

# Ensure hostname resolves as jevos-v4 on ichivol network
# (container name is already jevos-v4)

ENVF=deploy/vps/.env
TS=$(date +%Y%m%d_%H%M%S)
cp -a "$ENVF" "/opt/ichivol-backup/vps-env-pre-jevos-wire-$TS"

set_kv() {
  local key="$1" val="$2"
  if grep -q "^${key}=" "$ENVF"; then
    sed -i "s|^${key}=.*|${key}=${val}|" "$ENVF"
  else
    printf "%s=%s\n" "$key" "$val" >> "$ENVF"
  fi
}

set_kv JEV_PROVIDER jevos
set_kv JEV_URL "http://jevos-v4:8017"
set_kv JEV_MODEL jev-latest
set_kv JEV_SHADOW_ENABLED true
set_kv JEV_API_KEY "$JEV_KEY"

echo "=== env after (masked) ==="
grep -E '^(JEV_|TYPESAFE_|EVE_PAPER)' "$ENVF" | sed 's/\(KEY=\).*/\1***MASKED***/'

echo "=== recreate engine with new env ==="
docker compose --env-file deploy/vps/.env up -d --no-deps --force-recreate engine

sleep 5

echo "=== engine env ==="
docker exec ichivol-engine printenv | grep -E '^(JEV_|TYPESAFE_)' | sed 's/\(KEY=\).*/\1***MASKED***/'

echo "=== probe jevos /health from engine ==="
docker exec ichivol-engine python - <<'PY'
import os, urllib.request
base = os.getenv("JEV_URL", "http://jevos-v4:8017").rstrip("/")
url = base + "/health"
try:
    with urllib.request.urlopen(url, timeout=8) as r:
        print("OK", url, r.status, r.read()[:180])
except Exception as e:
    print("FAIL", url, type(e).__name__, e)
PY

echo "=== adapter health ==="
docker exec ichivol-engine python - <<'PY'
from app.jev.adapter import health
h = health(provider="jevos")
print(h)
PY

echo "=== DONE ==="
