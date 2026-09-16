#!/bin/bash
set -euo pipefail
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
  SELECT 'CREATE DATABASE ichivol_engine'
  WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'ichivol_engine')\gexec
EOSQL
