#!/usr/bin/env bash
#
# refresh-staging.sh — Refresca el entorno de STAGING a partir de PRODUCCION.
#
# Flujo (el orden NO es negociable):
#   1. Dump de la base de produccion (pg_dump -Fc) — solo LECTURA sobre prod.
#   2. Copia del filestore de produccion (adjuntos).
#   3. Se detiene el Odoo de staging y se recrea su base desde el dump.
#   4. Se restaura el filestore en staging.
#   5. NEUTRALIZACION de la base de staging (correo, crons, pagos, IAP, banca,
#      envios, indexacion). Se hace con el Odoo PARADO: staging nunca llega a
#      servir datos de produccion sin neutralizar.
#   6. Se fija web.base.url al dominio de staging y se congela.
#   7. (Opcional) Ofuscacion de datos personales (--anonymize).
#   8. Se arranca el Odoo de staging.
#
# Diseñado para produccion: falla ruidoso (set -euo pipefail), verifica que el
# destino NUNCA sea produccion, pide confirmacion y limpia sus temporales.
#
# Requisitos: ejecutarse en el HOST donde corren ambos stacks (acceso a
# 'docker'). Prod y staging pueden compartir servidor de base o no.
#
# Uso:
#   scripts/refresh-staging.sh [-y] [--anonymize] [--keep-tmp]
#
#   -y, --yes         No preguntar confirmacion (para cron/CI).
#   --anonymize       Ofusca emails/logins tras neutralizar (privacidad).
#   --keep-tmp        No borra el dump/filestore temporales al terminar.
#
# La configuracion se lee de scripts/refresh-staging.env (ver .example).

set -euo pipefail

# --- Localizacion y carga de configuracion -------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${REFRESH_ENV_FILE:-$SCRIPT_DIR/refresh-staging.env}"

if [ ! -f "$ENV_FILE" ]; then
  echo "ERROR: no existe el archivo de configuracion: $ENV_FILE" >&2
  echo "Copia scripts/refresh-staging.env.example y rellenalo." >&2
  exit 1
fi
# shellcheck disable=SC1090
. "$ENV_FILE"

# --- Flags ----------------------------------------------------------------
ASSUME_YES=0
ANONYMIZE=0
KEEP_TMP=0
for arg in "$@"; do
  case "$arg" in
    -y|--yes)      ASSUME_YES=1 ;;
    --anonymize)   ANONYMIZE=1 ;;
    --keep-tmp)    KEEP_TMP=1 ;;
    *) echo "Argumento desconocido: $arg" >&2; exit 1 ;;
  esac
done

log() { printf '\033[1;34m[%s]\033[0m %s\n' "$(date +%H:%M:%S)" "$*"; }
die() { printf '\033[1;31mERROR:\033[0m %s\n' "$*" >&2; exit 1; }

# --- Validacion de configuracion -----------------------------------------
required="PROD_DB_CONTAINER PROD_ODOO_CONTAINER STAGING_DB_CONTAINER \
STAGING_ODOO_CONTAINER PROD_DB STAGING_DB PROD_DB_USER PROD_DB_PASSWORD \
STAGING_ADMIN_USER STAGING_ADMIN_PASSWORD APP_DB_USER APP_DB_PASSWORD \
STAGING_BASE_URL"
for v in $required; do
  eval "val=\${$v:-}"
  [ -n "$val" ] || die "Falta la variable '$v' en $ENV_FILE"
done

# --- Barreras de seguridad: NUNCA tocar produccion -----------------------
[ "$STAGING_DB" != "$PROD_DB" ] \
  || die "STAGING_DB y PROD_DB son iguales ('$STAGING_DB'). Abortando."
[ "$STAGING_DB_CONTAINER" != "$PROD_DB_CONTAINER" ] \
  || die "El contenedor de BD de staging es el de produccion. Abortando."
[ "$STAGING_ODOO_CONTAINER" != "$PROD_ODOO_CONTAINER" ] \
  || die "El contenedor de Odoo de staging es el de produccion. Abortando."

# Verifica que los contenedores existen antes de empezar.
for c in "$PROD_DB_CONTAINER" "$PROD_ODOO_CONTAINER" \
         "$STAGING_DB_CONTAINER" "$STAGING_ODOO_CONTAINER"; do
  docker inspect "$c" >/dev/null 2>&1 || die "Contenedor no encontrado: $c"
done

STAGING_ODOO_IMAGE="$(docker inspect -f '{{.Config.Image}}' "$STAGING_ODOO_CONTAINER")"

cat <<EOF

  Se va a RECREAR la base de staging desde produccion:

    Produccion (solo lectura):  $PROD_DB   @ $PROD_DB_CONTAINER
    Staging  (SE BORRA Y RECREA): $STAGING_DB @ $STAGING_DB_CONTAINER
    Neutralizar: SI      Anonimizar: $([ "$ANONYMIZE" = 1 ] && echo SI || echo no)
    web.base.url -> $STAGING_BASE_URL

EOF
if [ "$ASSUME_YES" != 1 ]; then
  printf "Escribe 'staging' para continuar: "
  read -r confirm
  [ "$confirm" = "staging" ] || die "Cancelado."
fi

# --- Temporales -----------------------------------------------------------
TMPDIR="$(mktemp -d)"
cleanup() { [ "$KEEP_TMP" = 1 ] || rm -rf "$TMPDIR"; }
trap cleanup EXIT
DUMP="$TMPDIR/prod.dump"
FILESTORE="$TMPDIR/filestore.tgz"

# Helpers para ejecutar psql/pg_* dentro de los contenedores de BD.
prod_db()    { docker exec -e PGPASSWORD="$PROD_DB_PASSWORD" "$PROD_DB_CONTAINER" "$@"; }
stg_admin()  { docker exec -e PGPASSWORD="$STAGING_ADMIN_PASSWORD" "$STAGING_DB_CONTAINER" "$@"; }
stg_app()    { docker exec -e PGPASSWORD="$APP_DB_PASSWORD" "$STAGING_DB_CONTAINER" "$@"; }

# =========================================================================
# 1. Dump de produccion (solo lectura)
# =========================================================================
log "1/8 Dump de produccion ($PROD_DB)..."
prod_db pg_dump -U "$PROD_DB_USER" -Fc -d "$PROD_DB" > "$DUMP"
[ -s "$DUMP" ] || die "El dump de produccion salio vacio."
log "    dump: $(du -h "$DUMP" | cut -f1)"

# =========================================================================
# 2. Filestore de produccion
# =========================================================================
log "2/8 Copiando filestore de produccion..."
if docker exec "$PROD_ODOO_CONTAINER" test -d "/var/lib/odoo/filestore/$PROD_DB"; then
  docker exec "$PROD_ODOO_CONTAINER" \
    tar czf - -C "/var/lib/odoo/filestore" "$PROD_DB" > "$FILESTORE"
  log "    filestore: $(du -h "$FILESTORE" | cut -f1)"
else
  log "    (produccion aun no tiene filestore; se omite)"
  : > "$FILESTORE"
fi

# =========================================================================
# 3. Parar staging y recrear su base
# =========================================================================
log "3/8 Parando Odoo de staging y recreando la base..."
docker stop "$STAGING_ODOO_CONTAINER" >/dev/null

# Cortar conexiones colgadas a la base de staging antes de borrarla.
stg_admin psql -U "$STAGING_ADMIN_USER" -d postgres -v ON_ERROR_STOP=1 -c \
  "SELECT pg_terminate_backend(pid) FROM pg_stat_activity
     WHERE datname='$STAGING_DB' AND pid <> pg_backend_pid();" >/dev/null || true

stg_admin dropdb   -U "$STAGING_ADMIN_USER" --if-exists "$STAGING_DB"
stg_admin createdb -U "$STAGING_ADMIN_USER" -O "$APP_DB_USER" "$STAGING_DB"

# Extensiones que exigen superusuario (si tu prod las usa). Vacio por defecto.
for ext in ${STAGING_EXTENSIONS:-}; do
  log "    creando extension '$ext' como admin..."
  stg_admin psql -U "$STAGING_ADMIN_USER" -d "$STAGING_DB" -v ON_ERROR_STOP=1 \
    -c "CREATE EXTENSION IF NOT EXISTS \"$ext\";"
done

# =========================================================================
# 4. Restaurar dump + filestore en staging
# =========================================================================
log "4/8 Restaurando la base en staging..."
# Se restaura como el ROL DE APLICACION: los objetos quedan de su propiedad,
# igual que en produccion. pg_restore puede emitir avisos ignorables.
set +e
docker exec -i -e PGPASSWORD="$APP_DB_PASSWORD" "$STAGING_DB_CONTAINER" \
  pg_restore -U "$APP_DB_USER" --no-owner --no-privileges \
             --jobs=4 -d "$STAGING_DB" < "$DUMP"
rc=$?
set -e
[ "$rc" -eq 0 ] || log "    pg_restore termino con avisos (rc=$rc); continuo."

log "    Restaurando filestore en staging..."
# Siempre se limpia el filestore viejo de staging; solo se extrae si prod tenia.
docker run --rm --volumes-from "$STAGING_ODOO_CONTAINER" \
  --entrypoint sh "$STAGING_ODOO_IMAGE" -c \
  "rm -rf '/var/lib/odoo/filestore/$STAGING_DB' \
   && mkdir -p '/var/lib/odoo/filestore/$STAGING_DB'"
if [ -s "$FILESTORE" ]; then
  docker run --rm -i --volumes-from "$STAGING_ODOO_CONTAINER" \
    --entrypoint sh "$STAGING_ODOO_IMAGE" -c \
    "tar xzf - -C '/var/lib/odoo/filestore/$STAGING_DB' --strip-components=1" \
    < "$FILESTORE"
fi

# =========================================================================
# 5. NEUTRALIZAR (con Odoo parado; staging aun no sirve nada)
# =========================================================================
log "5/8 Neutralizando la base de staging..."
# Se lanza como proceso efimero que comparte la red del contenedor de BD de
# staging (asi la alcanza en 127.0.0.1) y usa el addons_path del odoo.conf de
# la imagen, para que corran los neutralize.sql de TODOS los modulos.
docker run --rm \
  --network "container:$STAGING_DB_CONTAINER" \
  --entrypoint python3 "$STAGING_ODOO_IMAGE" \
  -m odoo neutralize -c /etc/odoo/odoo.conf \
    --db_host=127.0.0.1 --db_port=5432 \
    --db_user="$APP_DB_USER" --db_password="$APP_DB_PASSWORD" \
    -d "$STAGING_DB"

# =========================================================================
# 6. Fijar web.base.url al dominio de staging y congelarlo
# =========================================================================
log "6/8 Fijando web.base.url -> $STAGING_BASE_URL"
stg_app psql -U "$APP_DB_USER" -d "$STAGING_DB" -v ON_ERROR_STOP=1 <<SQL
INSERT INTO ir_config_parameter (key, value)
     VALUES ('web.base.url', '$STAGING_BASE_URL')
ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value;
INSERT INTO ir_config_parameter (key, value)
     VALUES ('web.base.url.freeze', 'True')
ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value;
SQL

# =========================================================================
# 7. (Opcional) Ofuscacion de datos personales
# =========================================================================
if [ "$ANONYMIZE" = 1 ]; then
  log "7/8 Ofuscando datos personales..."
  stg_app psql -U "$APP_DB_USER" -d "$STAGING_DB" -v ON_ERROR_STOP=1 <<'SQL'
UPDATE res_partner
   SET email = 'partner_' || id || '@example.com'
 WHERE email IS NOT NULL AND email <> '';
UPDATE res_partner SET phone = NULL, mobile = NULL;
UPDATE res_users
   SET login = 'user_' || id || '@example.com'
 WHERE login NOT IN ('__system__');
SQL
else
  log "7/8 Ofuscacion omitida (usa --anonymize si staging tiene ojos ajenos)."
fi

# =========================================================================
# 8. Arrancar staging
# =========================================================================
log "8/8 Arrancando Odoo de staging..."
docker start "$STAGING_ODOO_CONTAINER" >/dev/null

log "Listo. Staging refrescado y NEUTRALIZADO desde produccion."
log "Comprueba el banner rojo de 'base neutralizada' al entrar."
