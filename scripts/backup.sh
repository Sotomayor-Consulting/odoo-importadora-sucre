#!/usr/bin/env bash
#
# backup.sh — Backup de produccion de Odoo: base de datos + filestore.
#
# Un backup de Odoo solo sirve si lleva LAS DOS PARTES (doc oficial):
#   - la base PostgreSQL  (pg_dump -Fc, formato custom, comprimido)
#   - el filestore        (adjuntos, imagenes; en el volumen odoo-data)
# Un dump sin su filestore deja los adjuntos rotos al restaurar.
#
# Cada ejecucion crea un "punto de restauracion" con marca de tiempo:
#   $BACKUP_DIR/<STAMP>/database.dump
#   $BACKUP_DIR/<STAMP>/filestore.tgz
#   $BACKUP_DIR/<STAMP>/manifest.txt
# y lo sube a Cloudflare R2 (offsite). Guarda copia local unos dias.
#
# Pensado para cron en el HOST (necesita 'docker' y, para offsite, 'aws').
# Config en scripts/backup.env (ver .example). Se ejecuta:
#
#   scripts/backup.sh
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${BACKUP_ENV_FILE:-$SCRIPT_DIR/backup.env}"

[ -f "$ENV_FILE" ] || { echo "ERROR: falta $ENV_FILE (copia backup.env.example)" >&2; exit 1; }
# shellcheck disable=SC1090
. "$ENV_FILE"

log() { printf '\033[1;34m[%s]\033[0m %s\n' "$(date +'%F %T')" "$*"; }
die() { printf '\033[1;31mERROR:\033[0m %s\n' "$*" >&2; exit 1; }

# --- Validacion -----------------------------------------------------------
required="DB_CONTAINER ODOO_CONTAINER DB DB_USER DB_PASSWORD BACKUP_DIR"
for v in $required; do
  eval "val=\${$v:-}"
  [ -n "$val" ] || die "Falta la variable '$v' en $ENV_FILE"
done
docker inspect "$DB_CONTAINER"   >/dev/null 2>&1 || die "Contenedor no encontrado: $DB_CONTAINER"
docker inspect "$ODOO_CONTAINER" >/dev/null 2>&1 || die "Contenedor no encontrado: $ODOO_CONTAINER"

# --- Evitar solapes (un backup a la vez) ----------------------------------
mkdir -p "$BACKUP_DIR"
exec 9>"$BACKUP_DIR/.lock"
flock -n 9 || die "Ya hay un backup en curso."

STAMP="$(date +'%Y-%m-%d_%H-%M-%S')"
DEST="$BACKUP_DIR/$STAMP"
mkdir -p "$DEST"

# Si algo falla, no dejar un punto de restauracion a medias.
trap '[ -n "${OK:-}" ] || { rm -rf "$DEST"; echo "Backup abortado, temporal limpiado." >&2; }' EXIT

# =========================================================================
# 1. Base de datos (pg_dump -Fc: custom, comprimido, restaurable en paralelo)
# =========================================================================
log "Dump de la base '$DB'..."
docker exec -e PGPASSWORD="$DB_PASSWORD" "$DB_CONTAINER" \
  pg_dump -U "$DB_USER" -Fc -d "$DB" > "$DEST/database.dump"
[ -s "$DEST/database.dump" ] || die "El dump salio vacio."
log "  database.dump: $(du -h "$DEST/database.dump" | cut -f1)"

# =========================================================================
# 2. Filestore
# =========================================================================
log "Copiando filestore..."
if docker exec "$ODOO_CONTAINER" test -d "/var/lib/odoo/filestore/$DB"; then
  docker exec "$ODOO_CONTAINER" \
    tar czf - -C "/var/lib/odoo/filestore" "$DB" > "$DEST/filestore.tgz"
  log "  filestore.tgz: $(du -h "$DEST/filestore.tgz" | cut -f1)"
else
  log "  (sin filestore todavia; se crea vacio)"
  : > "$DEST/filestore.tgz"
fi

# =========================================================================
# 3. Manifiesto (para restaurar en un entorno compatible)
# =========================================================================
{
  echo "timestamp=$STAMP"
  echo "database=$DB"
  echo "pg_dump_format=custom"
  echo "postgres=$(docker exec "$DB_CONTAINER" postgres --version 2>/dev/null | awk '{print $3}')"
  echo "odoo_image=$(docker inspect -f '{{.Config.Image}}' "$ODOO_CONTAINER")"
} > "$DEST/manifest.txt"

# =========================================================================
# 4. Subida offsite a R2 (lo importante: un backup local muere con el VPS)
# =========================================================================
if [ -n "${R2_BUCKET:-}" ] && [ -n "${R2_ENDPOINT:-}" ]; then
  log "Subiendo a R2: s3://$R2_BUCKET/${R2_PREFIX:-odoo-backups}/$STAMP/ ..."
  AWS_ACCESS_KEY_ID="${AWS_ACCESS_KEY_ID:-}" \
  AWS_SECRET_ACCESS_KEY="${AWS_SECRET_ACCESS_KEY:-}" \
  aws s3 cp --recursive "$DEST" \
    "s3://$R2_BUCKET/${R2_PREFIX:-odoo-backups}/$STAMP/" \
    --endpoint-url "$R2_ENDPOINT" --only-show-errors
  log "  Subida completada."
else
  log "R2 no configurado: backup SOLO local. Configura R2_* para tener offsite."
fi

# =========================================================================
# 5. Retencion local (el borrado en R2 se hace con una regla de ciclo de vida
#    del bucket, mas segura que borrar desde el cliente)
# =========================================================================
RETENTION_DAYS="${RETENTION_DAYS:-7}"
log "Reteniendo backups locales de los ultimos $RETENTION_DAYS dias..."
find "$BACKUP_DIR" -mindepth 1 -maxdepth 1 -type d -mtime "+$RETENTION_DAYS" \
  -exec rm -rf {} + 2>/dev/null || true

OK=1
log "Backup completo: $DEST"
