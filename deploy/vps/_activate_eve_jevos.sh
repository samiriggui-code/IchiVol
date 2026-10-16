#!/bin/bash
set -euo pipefail
cd /opt/ichivol

# arg1 = TYPESAFE_API_KEY (JEV API primary). arg2 = optional local jevos key (fallback).
TS_KEY="${1:?need TYPESAFE_API_KEY as arg1}"
JEVOS_KEY="${2:-}"

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

# JEV API calculates; jevos only when API has no credits left.
set_kv JEV_PROVIDER typesafe
set_kv JEV_FALLBACK jevos
set_kv TYPESAFE_API_URL 'https://api.typesafe.ai'
set_kv TYPESAFE_API_KEY "$TS_KEY"
set_kv JEV_URL 'http://jevos-v4:8017'
set_kv JEV_MODEL jev-latest
set_kv JEV_SHADOW_ENABLED true
if [ -n "$JEVOS_KEY" ]; then
  set_kv JEV_API_KEY "$JEVOS_KEY"
fi
set_kv EVE_PAPER_AUTONOMY true
set_kv EVENT_RADAR_ENABLED true
set_kv EVENT_RADAR_CRYPTO_RSS_ENABLED true
set_kv EVENT_RADAR_YAHOO_FINANCE_RSS_ENABLED true
set_kv EVENT_RADAR_SEC_EDGAR_ENABLED true

echo '=== env masked ==='
grep -E '^(JEV_|TYPESAFE_|EVE_|EVENT_RADAR)' "$ENVF" | sed 's/\(KEY=\).*/\1***MASKED***/'

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
docker exec ichivol-engine printenv | grep -E '^(JEV_|TYPESAFE_|EVE_|EVENT_RADAR)' | sed 's/\(KEY=\).*/\1***MASKED***/'
docker exec ichivol-engine python -c 'from app.jev.providers import resolve_provider, resolve_fallback_provider; p=resolve_provider(); f=resolve_fallback_provider(); print("primary", p.name, p.base_url); print("fallback", None if f is None else f.name)'
docker exec ichivol-engine python -c 'from app.jev.adapter import health; print("typesafe", health(provider="typesafe")); print("jevos", health(provider="jevos"))'
docker exec ichivol-engine python -c 'from app.eve.calibration import active_policy; r=active_policy()["routing"]; print({k:r[k] for k in r if "use_jev" in k or "primitives" in k})'
curl -fsS -m 15 http://127.0.0.1:3060/api/health; echo
echo DONE
