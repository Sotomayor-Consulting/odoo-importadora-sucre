#!/bin/sh
set -e

# Equivalente propio del entrypoint oficial: construye los argumentos de
# conexion desde el entorno. Solo los añade si no estan ya en odoo.conf,
# para que el archivo siga mandando sobre las variables.
: "${HOST:=db}"
: "${PORT:=5432}"
: "${USER:=odoo}"
: "${PASSWORD:=odoo}"
: "${DB_NAME:=importadora_sucre}"

DB_ARGS=""
add_arg() {
  if ! grep -qE "^[[:space:]]*$1[[:space:]]*=" "$ODOO_RC" 2>/dev/null; then
    DB_ARGS="$DB_ARGS --$1=$2"
  fi
}
add_arg db_host "$HOST"
add_arg db_port "$PORT"
add_arg db_user "$USER"
add_arg db_password "$PASSWORD"

# Master password: se inyecta desde el entorno (una sola vez) para no
# versionarla. Sin gestor web (list_db=False) su exposicion es minima, pero
# es la red de seguridad si alguien reactiva la gestion de bases.
if [ -n "$ADMIN_PASSWD" ] && ! grep -qE "^[[:space:]]*admin_passwd[[:space:]]*=" "$ODOO_RC" 2>/dev/null; then
  printf '\nadmin_passwd = %s\n' "$ADMIN_PASSWD" >> "$ODOO_RC"
fi

# Inicializacion de la base la PRIMERA vez. Con list_db=False no existe el
# gestor web, asi que la creacion inicial se hace aqui: idempotente (solo si la
# base no existe) y sin datos demo. En arranques posteriores no hace nada.
# SKIP_DB_INIT=1 lo desactiva (util para restauraciones manuales).
if [ -z "$SKIP_DB_INIT" ]; then
  if ! PGPASSWORD="$PASSWORD" psql -h "$HOST" -p "$PORT" -U "$USER" -d postgres -tAc \
        "SELECT 1 FROM pg_database WHERE datname='$DB_NAME'" 2>/dev/null | grep -q 1; then
    echo "Base '$DB_NAME' inexistente: inicializando (modulo base, sin demo)..."
    python3 -m odoo -c "$ODOO_RC" $DB_ARGS -d "$DB_NAME" -i base \
      --without-demo=all --stop-after-init
  fi
fi

# Actualizacion de modulos (aplica migraciones del nuevo fuente/addons).
# Se dispara SOLO cuando UPGRADE trae un valor, y corre una vez antes de
# arrancar los workers. Ver el "Ritual de actualizacion" en la doc.
#   UPGRADE=all            -> actualiza todos los modulos instalados
#   UPGRADE=modulo_a,modulo_b -> actualiza solo esos
# Tras el despliegue de actualizacion, vaciar UPGRADE para que los arranques
# normales no repitan la actualizacion (es lenta y no debe correr en cada boot).
if [ -n "${UPGRADE:-}" ]; then
  echo "Actualizando modulos ($UPGRADE) en '$DB_NAME'..."
  python3 -m odoo -c "$ODOO_RC" $DB_ARGS -d "$DB_NAME" -u "$UPGRADE" --stop-after-init
fi

exec python3 -m odoo -c "$ODOO_RC" $DB_ARGS "$@"
