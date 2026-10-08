# Backups — base de datos + filestore

Un backup de Odoo **solo sirve si contiene las dos partes**: la base PostgreSQL
**y** el filestore (adjuntos, imágenes). Un dump de la base sin su filestore deja
los documentos rotos al restaurar. Es la regla que marca la
[doc oficial de Odoo](https://www.odoo.com/documentation/19.0/administration/on_premise/deploy.html).

Comando: `odoo-backup` (fuente en [`ops/bin/odoo-backup`](../ops/bin/odoo-backup)).

---

## 1. Cómo funciona

`odoo-backup` se ejecuta **dentro del contenedor de Odoo**, no en el servidor.
Usa el comando nativo de Odoo:

```bash
odoo-bin db dump <base> <archivo.zip>
```

que genera **un único `.zip`** con:

| Dentro del zip | Qué es |
|---|---|
| `dump.sql` | La base de datos |
| `filestore/` | Los adjuntos |
| `manifest.json` | Versión de Odoo y de PostgreSQL, y módulos instalados |

Es el mismo formato de backup de Odoo.sh. La base y sus adjuntos viajan siempre
juntos y coherentes entre sí, y el archivo se restaura con `odoo-bin db load` en
cualquier Odoo de la misma versión.

**Por qué dentro del contenedor.** Ahí ya están la conexión a la base (variables
`PG*`), el filestore y el cliente de PostgreSQL de la versión correcta. No hace
falta `sudo`, ni `docker exec`, ni conocer nombres de contenedores, ni instalar
nada en el servidor.

---

## 2. Qué hace cada ejecución

1. Vuelca la base a `/home/odoo/backups/daily/<base>_<AAAAMMDD_HHMMSS>.zip`.
2. Comprueba que el zip es íntegro y contiene `dump.sql` y `manifest.json`.
3. Lo promueve a `weekly/` (los domingos) y a `monthly/` (el día 1).
4. Aplica la retención local.
5. Lo sube a R2, con los mismos niveles.
6. Avisa al monitor, si hay uno configurado.

Si algo falla a mitad, no deja un zip a medias y el comando termina con error.
No pueden correr dos backups a la vez.

### Retención

Es el esquema de Odoo.sh:

| Nivel | Cuándo se crea | Copias que se conservan |
|---|---|---|
| `daily/` | Cada ejecución | 7 |
| `weekly/` | Domingos | 4 |
| `monthly/` | Día 1 de cada mes | 3 |

Una copia promovida es un **enlace duro**: el mismo archivo aparece en dos
niveles sin ocupar el doble. La primera ejecución deja ya una copia en cada
nivel, como punto de partida. Las fechas van en UTC.

### Dónde quedan

- **En el servidor:** volumen `odoo-backups`, montado en `/home/odoo/backups`.
  Restauración rápida, pero se pierde con el servidor.
- **En R2:** `s3://<bucket>/<ENV_NAME>/{daily,weekly,monthly}/`. La protección
  real. *Un backup que solo vive en el mismo servidor no es un backup.*

---

## 3. Configuración

Variables del servicio de Odoo en Dokploy (plantilla en
[`env.example`](../env.example)):

| Variable | Valor |
|---|---|
| `BACKUP_R2_BUCKET` | Bucket **propio** de backups (no el del tarball de Odoo) |
| `BACKUP_R2_ENDPOINT` | `https://<cuenta>.r2.cloudflarestorage.com` |
| `BACKUP_R2_ACCESS_KEY_ID` / `BACKUP_R2_SECRET_ACCESS_KEY` | Token del bucket |
| `BACKUP_HEALTHCHECK_URL` | Opcional. URL del monitor |
| `BACKUP_KEEP_DAILY` / `_WEEKLY` / `_MONTHLY` | Opcionales. Por defecto 7 / 4 / 3 |

Con `BACKUP_R2_BUCKET` vacío el backup queda **solo en el servidor** y el
comando lo avisa. Sirve para probar; no para producción.

### El token de R2

En Cloudflare: **R2 > Manage API Tokens > Create Account API Token**.

| Ajuste | Valor |
|---|---|
| Permissions | **Object Read & Write** |
| Specify bucket(s) | Solo el bucket de backups |
| TTL | Forever |

No reutilizar el token de solo lectura del build ni uno de administración. El
comando nunca borra en R2, así que no necesita más permisos que escribir.

### Retención en R2

La aplican las **reglas de ciclo de vida** del bucket, no el comando. Es más
seguro: un fallo del script no puede eliminar copias buenas. En el bucket,
**Settings > Object lifecycle rules**, una regla por prefijo:

| Prefijo | Borrar objetos tras |
|---|---|
| `prod/daily/` | 8 días |
| `prod/weekly/` | 35 días |
| `prod/monthly/` | 100 días |

Si staging también sube copias, repetir con `staging/`.

---

## 4. Ejecutarlo

A mano, desde el servidor:

```bash
docker compose exec odoo odoo-backup
```

### Programado, con Dokploy

En el servicio de Odoo, **Schedules > Add Schedule**:

| Campo | Valor |
|---|---|
| Service | `odoo` |
| Schedule | `30 7 * * *` (07:30 UTC = 02:30 en Ecuador) |
| Command | `odoo-backup` |

Cada ejecución queda con su registro en Dokploy.

### Que avise si deja de funcionar

Un backup que falla en silencio es peor que no tener backup. Con
`BACKUP_HEALTHCHECK_URL` apuntando a un monitor tipo
[healthchecks.io](https://healthchecks.io), el comando avisa al empezar, al
terminar y si falla. El monitor alerta por correo cuando **un día no llega el
aviso**, que es el caso que de otro modo nadie ve.

---

## 5. Restaurar

Todo se hace dentro del contenedor de Odoo, con comandos nativos.

### Recuperar producción desde un backup

```bash
odoo-bin db load --force --move <base> /home/odoo/backups/daily/<archivo>.zip
```

- `--force` borra la base actual si existe. **Es destructivo.**
- `--move` conserva el identificador de la base: es *la misma* base que
  vuelve, no una copia. Sin él, Odoo la trata como base nueva y la suscripción
  Enterprise puede dejar de reconocerla.

Después hay que **reiniciar el servicio** en Dokploy, para que los procesos de
Odoo dejen de usar lo que tenían en memoria de la base anterior.

> En una emergencia real, antes de restaurar saca un backup del estado roto con
> `odoo-backup`. Si el backup elegido resulta no ser el bueno, podrás volver.

### Traer una copia a otro entorno (staging)

```bash
odoo-bin db load --force --neutralize <base> <archivo>.zip
```

- Sin `--move`: la copia recibe un identificador nuevo.
- `--neutralize` desactiva correo saliente, acciones planificadas, proveedores
  de pago y demás integraciones **antes** de que la base sea visible para los
  procesos de Odoo.

El zip se baja de R2 al contenedor con cualquier cliente S3, o se copia con
`docker compose cp`.

---

## 6. Un backup sin probar no es un backup

La prueba es restaurarlo. La forma natural es el refresco de staging: si staging
se carga bien desde el backup de producción, la cadena completa funciona. Ver
[entornos-staging.md](entornos-staging.md).

Hacer esa prueba al menos una vez tras montar los backups, y cada vez que se
cambie de servidor o de versión de Odoo.

---

## 7. Scripts anteriores

`scripts/backup.sh` y `scripts/refresh-staging.sh` son los scripts originales,
que corren **en el servidor** y usan `docker exec`. Los sustituyen
`odoo-backup` y `odoo-refresh-staging`, que corren dentro del contenedor.

Se conservan solo hasta terminar la migración desde el proyecto antiguo de
Dokploy. No usar en el proyecto nuevo.
