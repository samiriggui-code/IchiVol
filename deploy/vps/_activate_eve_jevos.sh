#!/bin/bash
set -euo pipefail
cd /opt/ichivol

JEV_KEY="${1:?need JEV_API_KEY as arg1}"

ENVF=deploy/vps/.env
mkdir -p /opt/ichivol-backup
cp -a "$ENVF" "/opt/ichivol-backup/vps-env-pre-eve-modes-$(date +%Y%m%d_%H%M%S)"

set_kv() {
  local key="$1" val="$2"
  if grep -q "^${key}=" "$ENVF"; then
    sed -i "s|^${key}=.*|${key}=${val}|" "$ENVF"
  else
    printf '%s=%s\n' "$key" "$val" >> "$ENVF"
  fi
}

set_kv JEV_PROVIDER jevos
set_kv JEV_URL 'http://jevos-v4:8017'
set_kv JEV_MODEL jev-latest
set_kv JEV_SHADOW_ENABLED true
set_kv JEV_API_KEY "$JEV_KEY"
set_kv EVE_PAPER_AUTONOMY true
set_kv EVENT_RADAR_ENABLED true
set_kv EVENT_RADAR_CRYPTO_RSS_ENABLED true
set_kv EVENT_RADAR_YAHOO_FINANCE_RSS_ENABLED true
set_kv EVENT_RADAR_SEC_EDGAR_ENABLED true

echo '=== env masked ==='
grep -E '^(JEV_|EVE_|EVENT_RADAR)' "$ENVF" | sed 's/\(KEY=\).*/\1***MASKED***/'

# Connect jevos to ichivol docker network if needed
if ! docker inspect jevos-v4 --format '{{json .NetworkSettings.Networks}}' | grep -q '"ichivol"'; then
  echo '=== docker network connect jevos-v4 -> ichivol ==='
  docker network connect ichivol jevos-v4 || true
fi

echo '=== git pull latest ==='
git fetch origin cursor/eve-intelligence-v1-8626:refs/remotes/origin/cursor/eve-intelligence-v1-8626
git checkout cursor/eve-intelligence-v1-8626
git reset --hard origin/cursor/eve-intelligence-v1-8626
git log -1 --oneline

echo '=== rebuild engine+web ==='
docker compose --env-file deploy/vps/.env build engine web
docker compose --env-file deploy/vps/.env up -d --no-deps --force-recreate engine web
sleep 6

echo '=== probes ==='
docker exec ichivol-engine printenv | grep -E '^(JEV_|EVE_|EVENT_RADAR)' | sed 's/\(KEY=\).*/\1***MASKED***/'
docker exec ichivol-engine python -c 'import urllib.request; print(urllib.request.urlopen("http://jevos-v4:8017/health", timeout=8).read()[:120])'
docker exec ichivol-engine python -c 'from app.jev.adapter import health; print(health(provider="jevos"))'
docker exec ichivol-engine python -c 'from app.eve.calibration import active_policy; r=active_policy()["routing"]; print({k:r[k] for k in r if "use_jev" in k or "primitives" in k})'
curl -fsS -m 15 http://127.0.0.1:3060/api/health; echo
echo DONE
