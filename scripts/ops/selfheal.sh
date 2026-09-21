#!/bin/sh
# IchiVol self-heal + backups. Runs from cron on the VPS. Read-mostly: it only restarts the engine when the paper
# loop has stopped writing equity snapshots, and dumps the databases once a day. It never touches trading data.
LOG=/var/log/ichivol-selfheal.log
PSQL="docker exec -i ichivol-postgres psql -U ichivol -d ichivol_engine -At"
now() { date -u +%FT%TZ; }

age=$($PSQL -c "select coalesce(extract(epoch from now() - max(timestamp))::int, 999999) from paper_equity_snapshots" 2>/dev/null)
if [ -z "$age" ]; then
  echo "$(now) postgres unreachable, restarting postgres" >> $LOG
  docker restart ichivol-postgres >/dev/null 2>&1
  exit 0
fi
# snapshots are written every 5 min; 20 min without one = the loop is dead or hung
if [ "$age" -gt 1200 ]; then
  echo "$(now) no equity snapshot for ${age}s -> restarting engine" >> $LOG
  docker restart ichivol-engine >/dev/null 2>&1
fi
for c in ichivol-engine ichivol-server ichivol-web; do
  st=$(docker inspect -f '{{.State.Running}}' $c 2>/dev/null)
  if [ "$st" != "true" ]; then echo "$(now) $c not running -> start" >> $LOG; docker start $c >/dev/null 2>&1; fi
done

# one dump per day (03:xx UTC), keep 14 days
if [ "$(date -u +%H)" = "03" ] && [ ! -f /opt/backups/auto_$(date -u +%F)_engine.dump ]; then
  docker exec ichivol-postgres pg_dump -U ichivol -Fc ichivol_engine > /opt/backups/auto_$(date -u +%F)_engine.dump
  docker exec ichivol-postgres pg_dump -U ichivol -Fc ichivol > /opt/backups/auto_$(date -u +%F)_server.dump
  find /opt/backups -name 'auto_*' -mtime +14 -delete
  echo "$(now) daily backup done" >> $LOG
fi
