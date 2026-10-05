#!/usr/bin/env bash
# Nightly backup: database dump + uploaded files, kept for 14 days.
# Cron (as root):  15 3 * * * /opt/scarlett-embroidery/deploy/backup.sh >> /var/log/scarlett-backup.log 2>&1
# Copy /opt/scarlett-backups off the server now and then (e.g. scp or rclone to cloud storage).
set -euo pipefail
cd "$(dirname "$0")/.."
DEST=/opt/scarlett-backups
STAMP=$(date +%Y%m%d-%H%M)
mkdir -p "$DEST"
C="docker compose -f docker-compose.prod.yml"

$C exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB"' | gzip > "$DEST/db-$STAMP.sql.gz"

for vol in media private_media; do
  docker run --rm -v "scarlett-prod_${vol}:/data:ro" -v "$DEST:/out" alpine \
    tar czf "/out/${vol}-$STAMP.tar.gz" -C /data .
done

find "$DEST" -type f -mtime +14 -delete
echo "Backup $STAMP done"
