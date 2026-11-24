#!/usr/bin/env bash
# Requires explicitly configured host, Docker Compose, and private backup directory.
set -Eeuo pipefail
umask 077
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
project_root="$(git rev-parse --show-toplevel)"
backup_root="${1:?Pass an existing absolute private backup directory}"
[[ "$backup_root" = /* && -d "$backup_root" && ! -L "$backup_root" ]] || { echo "Invalid backup directory" >&2; exit 1; }
backup_root="$(realpath "$backup_root")"
case "$backup_root/" in "$project_root/"*) echo "Backup outside repository required" >&2; exit 1;; esac
[[ "$(stat -c '%a' "$backup_root")" = 700 ]] || { echo "Backup directory must be mode 700" >&2; exit 1; }
exec 9>"$backup_root/.backup-lock"
flock -n 9 || { echo "Backup already running" >&2; exit 1; }
stamp="$(date -u +%Y%m%dT%H%M%SZ)-$(git rev-parse --short HEAD)"
work="$(mktemp -d "$backup_root/.work-$stamp-XXXXXX")"
paused=0
cleanup() {
    result=$?
    if ((paused)); then docker compose up -d --wait || result=1; fi
    if ((result)); then echo "Backup incomplete: $work; retained for inspection" >&2; fi
    exit "$result"
}
trap cleanup EXIT
# Only a running, healthy instance may be backed up. Prevent accidental activation.
docker compose ps --status running --services | grep -qx app
docker compose ps --status running --services | grep -qx proxy
git -C "$project_root" diff --quiet HEAD -- backend deploy android-admin scripts docs .github
git -C "$project_root" archive --format=tar.gz -o "$work/source.tar.gz" HEAD -- . ':(exclude)archives/sepas'
git -C "$project_root" rev-parse HEAD > "$work/source-commit.txt"
tar -tzf "$work/source.tar.gz" > "$work/source-inventory.txt"
grep -qx 'backend/manage.py' "$work/source-inventory.txt"
grep -qx 'deploy/compose.yaml' "$work/source-inventory.txt"
mkdir "$work/data"
chown 10001:10001 "$work/data"
paused=1
docker compose stop proxy app
docker compose run --rm --no-deps -v "$work/data:/backups" app python ops/backup.py create --db /data/store.sqlite3 --media /media --output /backups/store.tar.gz
docker compose up -d --wait
paused=0
# Restore into a new directory, never the live volumes.
docker compose run --rm --no-deps -v "$work/data:/backups" app python ops/backup.py restore --archive /backups/store.tar.gz --destination /backups/restore-test
docker compose run --rm --no-deps -v "$work/data:/backups" app python -c 'import sqlite3; db=sqlite3.connect("/backups/restore-test/store.sqlite3"); assert db.execute("PRAGMA integrity_check").fetchone()==("ok",); db.execute("select count(*) from store_product").fetchone()'
# Recovery test uses temporary restored data. Keep the original backup, not a redundant plaintext copy.
rm -rf -- "$work/data/restore-test"
(
    cd "$work"
    sha256sum source.tar.gz source-commit.txt source-inventory.txt data/store.tar.gz > SHA256SUMS
    sha256sum -c SHA256SUMS
)
touch "$work/$stamp.complete"
mv -T -- "$work" "$backup_root/$stamp"
work="$backup_root/$stamp"
echo "Verified local backup: $work"
