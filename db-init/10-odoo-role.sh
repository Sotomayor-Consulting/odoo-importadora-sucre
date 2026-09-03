#!/bin/sh
# Se ejecuta UNA sola vez, en la inicializacion del contenedor de Postgres
# (solo cuando el volumen de datos esta vacio). Crea el rol de aplicacion que
# usa Odoo: con LOGIN y CREATEDB, pero SIN superusuario.
#
# Por que: POSTGRES_USER es el superusuario del contenedor y se reserva para
# administracion y backups. Odoo se conecta con un rol propio de privilegios
# minimos; asi, un modulo malicioso o una inyeccion no obtienen control total
# del servidor de base de datos. CREATEDB es lo unico que Odoo necesita para
# crear y gestionar sus propias bases.
set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres <<-SQL
  DO \$\$
  BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '${ODOO_DB_USER}') THEN
      CREATE ROLE "${ODOO_DB_USER}" WITH LOGIN CREATEDB PASSWORD '${ODOO_DB_PASSWORD}';
    END IF;
  END
  \$\$;
SQL

echo "Rol de aplicacion '${ODOO_DB_USER}' creado (LOGIN, CREATEDB, sin superusuario)."
