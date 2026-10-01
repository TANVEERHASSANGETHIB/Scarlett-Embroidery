#!/bin/sh
set -e

wait_for() {
  host="$1"; port="$2"; name="$3"
  echo "Waiting for $name at $host:$port..."
  i=0
  until nc -z "$host" "$port"; do
    i=$((i + 1))
    if [ "$i" -gt 60 ]; then
      echo "$name not reachable, giving up."
      exit 1
    fi
    sleep 1
  done
}

if [ -n "$DB_HOST" ]; then wait_for "$DB_HOST" "${DB_PORT:-5432}" "PostgreSQL"; fi
if [ -n "$REDIS_HOST" ]; then wait_for "$REDIS_HOST" "${REDIS_PORT:-6379}" "Redis"; fi

if [ "${RUN_MIGRATIONS:-0}" = "1" ]; then
  python manage.py migrate --noinput
fi

# Hosts without a shell (e.g. Render's free plan) set RUN_SEED=1 to create the
# pricing and first admin on boot. Safe to repeat: it never overwrites anything.
if [ "${RUN_SEED:-0}" = "1" ]; then
  python manage.py seed --no-demo
fi

exec "$@"
