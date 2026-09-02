#!/bin/sh
set -e

# Equivalente propio del entrypoint oficial: construye los argumentos de
# conexion desde el entorno. Solo los añade si no estan ya en odoo.conf,
# para que el archivo siga mandando sobre las variables.
: "${HOST:=db}"
: "${PORT:=5432}"
: "${USER:=odoo}"
: "${PASSWORD:=odoo}"

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

exec python3 -m odoo -c "$ODOO_RC" $DB_ARGS "$@"
