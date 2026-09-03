# Backups de producción — base de datos + filestore

Un backup de Odoo **solo sirve si contiene las dos partes**: la base PostgreSQL
**y** el filestore (adjuntos, imágenes). Un dump de BD sin su filestore deja los
documentos rotos al restaurar. Es la regla que marca la
[doc oficial de Odoo](https://www.odoo.com/documentation/19.0/administration/on_premise/deploy.html).

Script: [`scripts/backup.sh`](../scripts/backup.sh).

---

## 1. ¿Hay que montar volúmenes nuevos?

**No.** Los datos ya viven en volúmenes nombrados (`db-data` para Postgres y
`odoo-data` para el filestore) — por eso son respaldables. El backup se toma
**desde los contenedores en marcha** (`pg_dump` + `tar` del filestore); no se
tocan los volúmenes de la app.

Lo único que decides es **dónde caen los backups**:

- **Host** (`BACKUP_DIR`): restauración rápida, pero muere con el VPS.
- **Offsite (R2)**: la protección real. *Un backup en el mismo servidor no es un backup.*

El script hace las dos: guarda `RETENTION_DAYS` en el host **y** sube cada copia
a R2.

---

## 2. Qué genera cada ejecución

Un "punto de restauración" con marca de tiempo:

```
<BACKUP_DIR>/<STAMP>/
  database.dump    # pg_dump -Fc (custom, comprimido)
  filestore.tgz    # el filestore de la base
  manifest.txt     # versiones de Postgres/Odoo, nombre de base, fecha
```

y lo replica en `s3://<bucket>/<prefix>/<STAMP>/` en R2.

---

## 3. Configuración (una vez)

```bash
cp scripts/backup.env.example scripts/backup.env
# Rellena contenedores, credenciales de la base y del bucket R2.
```

`scripts/backup.env` está en `.gitignore`: **no se versiona**.

Para el offsite necesitas el CLI `aws` en el host y un **token de R2 con
escritura solo en ese bucket** (no reutilices credenciales de administración).

---

## 4. Programación (backup automático)

### Opción A — cron del host (simple y robusto)

```bash
# crontab -e  — diario a las 02:30
30 2 * * * /ruta/al/repo/scripts/backup.sh >> /var/log/odoo-backup.log 2>&1
```

### Opción B — tarea programada de Dokploy

Si prefieres no tocar el cron del sistema, Dokploy puede ejecutar
`scripts/backup.sh` como tarea programada. (Dokploy también trae backups de
base de datos nativos a S3; puedes usar esos en vez de este script si te basta
con la BD, pero **recuerda respaldar también el filestore**.)

### Retención en R2

Configura una **regla de ciclo de vida** en el bucket (p. ej. borrar objetos de
más de 30 días). Es más seguro que borrar desde el cliente y evita que un fallo
del script elimine copias buenas.

---

## 5. Restaurar (un backup sin probar NO es un backup)

Restaurar es el proceso inverso: crear la base, cargar el dump y colocar el
filestore. Con un punto de restauración `<STAMP>` descargado a `./restore`:

```bash
DB=importadora_sucre          # base destino
DBC=importadora-prod-db-1      # contenedor de Postgres
ODC=importadora-prod-odoo-1    # contenedor de Odoo
APP_USER=odoo                  # rol de aplicacion
ADMIN=odoo_admin               # superusuario (crea la base)

# 1) Parar Odoo para que no haya conexiones abiertas.
docker stop "$ODC"

# 2) Recrear la base (cuidado: reemplaza la actual).
docker exec -e PGPASSWORD=... "$DBC" dropdb   -U "$ADMIN" --if-exists "$DB"
docker exec -e PGPASSWORD=... "$DBC" createdb -U "$ADMIN" -O "$APP_USER" "$DB"

# 3) Cargar el dump (como rol de aplicacion, dueño de los objetos).
docker exec -i -e PGPASSWORD=... "$DBC" \
  pg_restore -U "$APP_USER" --no-owner --no-privileges -d "$DB" < ./restore/database.dump

# 4) Restaurar el filestore.
docker run --rm -i --volumes-from "$ODC" --entrypoint sh <imagen-odoo> -c \
  "rm -rf /var/lib/odoo/filestore/$DB && mkdir -p /var/lib/odoo/filestore/$DB \
   && tar xzf - -C /var/lib/odoo/filestore/$DB --strip-components=1" < ./restore/filestore.tgz

# 5) Arrancar Odoo.
docker start "$ODC"
```

> Restaurar en **producción** es destructivo: reemplaza la base actual. En una
> emergencia real, primero saca un backup del estado roto por si acaso.

---

## 6. Prueba tus backups sin arriesgar producción

La mejor prueba de restauración es el **refresco de staging**: el script
[`refresh-staging.sh`](../scripts/refresh-staging.sh) ya restaura la base y el
filestore de producción en staging (y los neutraliza). Si staging se refresca
bien, tu cadena de backup/restore funciona. Ver
[entornos-staging.md](entornos-staging.md).

Haz esta prueba de restauración **al menos una vez tras montar los backups** y
cada vez que cambies de servidor o de versión de Odoo.
