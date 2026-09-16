#!/bin/sh
set -eu
echo "[engine] alembic upgrade head"
python -m alembic upgrade head
exec "$@"
