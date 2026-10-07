#!/bin/sh
set -e

# La configuracion por entorno NO se construye aqui: Odoo 19 la lee sola de
# las variables PG* y ODOO_* (ver odoo.conf). Este script solo valida que
# esten, espera a la base, la inicializa la primera vez y arranca el servidor.

for v in PGHOST PGUSER PGPASSWORD PGDATABASE ODOO_ADMIN_PASSWD; do
  eval "val=\${$v:-}"
  if [ -z "$val" ]; then
    echo "FATAL: falta la variable de entorno $v (ver env.example)" >&2
    exit 1
  fi
done
: "${PGPORT:=5432}"
export PGPORT

ODOO_BIN=/home/odoo/src/odoo/odoo-bin

# Sin dbfilter explicito, se sirve unicamente la base configurada.
: "${ODOO_DBFILTER:=^${PGDATABASE}\$}"
export ODOO_DBFILTER

# Espera a que Postgres acepte conexiones. Con la base como servicio aparte no
# hay 'depends_on' que garantice el orden de arranque.
tries=0
until pg_isready -q -h "$PGHOST" -p "$PGPORT"; do
  tries=$((tries + 1))
  if [ "$tries" -ge 30 ]; then
    echo "FATAL: Postgres no responde en $PGHOST:$PGPORT tras 60 s" >&2
    exit 1
  fi
  sleep 2
done

# Inicializacion de la base la PRIMERA vez. Con list_db=False no existe el
# gestor web, asi que la creacion inicial se hace aqui: idempotente (solo si la
# base no existe) y sin datos demo (el valor por defecto en Odoo 19).
# SKIP_DB_INIT=1 lo desactiva (staging: la base se restaura desde produccion).
if [ -z "${SKIP_DB_INIT:-}" ]; then
  # Si la consulta falla (clave mala, rol inexistente) se aborta: un error de
  # conexion NO debe confundirse con "la base no existe".
  if ! exists=$(psql -d postgres -tAc \
        "SELECT 1 FROM pg_database WHERE datname='$PGDATABASE'"); then
    echo "FATAL: no se pudo consultar Postgres como '$PGUSER'" >&2
    exit 1
  fi
  if [ "$exists" != "1" ]; then
    echo "Base '$PGDATABASE' inexistente: inicializando (modulo base, sin demo)..."
    python3 "$ODOO_BIN" -c "$ODOO_RC" -d "$PGDATABASE" -i base --stop-after-init
  fi
fi

# Actualizacion de modulos (aplica migraciones del nuevo fuente/addons).
# Se dispara SOLO cuando UPGRADE trae un valor, y corre una vez antes de
# arrancar los workers. Ver el "Ritual de actualizacion" en la doc.
#   UPGRADE=all               -> actualiza todos los modulos instalados
#   UPGRADE=modulo_a,modulo_b -> actualiza solo esos
# Tras el despliegue de actualizacion, vaciar UPGRADE para que los arranques
# normales no repitan la actualizacion (es lenta y no debe correr en cada boot).
if [ -n "${UPGRADE:-}" ]; then
  echo "Actualizando modulos ($UPGRADE) en '$PGDATABASE'..."
  python3 "$ODOO_BIN" -c "$ODOO_RC" -d "$PGDATABASE" -u "$UPGRADE" --stop-after-init
fi

exec python3 "$ODOO_BIN" -c "$ODOO_RC" "$@"
