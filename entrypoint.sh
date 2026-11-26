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

# Actualizacion de modulos, antes de arrancar los workers.
#
# Por defecto es AUTOMATICA, con la regla de Odoo.sh: se actualiza cada modulo
# instalado cuya version en __manifest__.py sea mayor que la registrada en la
# base. Si no subio ninguna version, no se actualiza nada y el arranque no se
# alarga. Quien cambie modelos, vistas o datos de un modulo debe subir su
# version; si no, el cambio llega al codigo pero no a la base.
#
#   UPGRADE=            -> automatico (lo normal; no hay que tocar nada)
#   UPGRADE=all         -> todos los modulos instalados. Para cuando cambia el
#                          fuente de Odoo, cuyos modulos no suben de version
#                          entre compilaciones. Vaciar despues.
#   UPGRADE=mod_a,mod_b -> solo esos, sin mirar versiones. Vaciar despues.
#   UPGRADE=none        -> nada.
#
# Si la actualizacion falla, el contenedor no arranca: es preferible a servir
# codigo nuevo sobre un esquema viejo. El motivo queda en el log.
run_upgrade() {
  echo "Actualizando modulos ($1) en '$PGDATABASE'..."
  python3 "$ODOO_BIN" -c "$ODOO_RC" -d "$PGDATABASE" -u "$1" --stop-after-init
}

case "${UPGRADE:-}" in
  none)
    echo "Actualizacion de modulos desactivada (UPGRADE=none)." ;;
  "")
    rc=0
    modules=$(odoo-modules-to-upgrade "$PGDATABASE") || rc=$?
    case "$rc" in
      0)
        if [ -n "$modules" ]; then
          run_upgrade "$modules"
        else
          echo "Modulos al dia: ninguna version subio."
        fi ;;
      3)
        # Staging recien creado, antes de cargarle la copia de produccion.
        echo "La base '$PGDATABASE' aun no existe o esta vacia: nada que actualizar." ;;
      *)
        echo "FATAL: no se pudo comprobar que modulos actualizar." >&2
        exit 1 ;;
    esac ;;
  *)
    run_upgrade "$UPGRADE" ;;
esac

exec python3 "$ODOO_BIN" -c "$ODOO_RC" "$@"
