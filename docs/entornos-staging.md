# Entornos: producción y staging (base neutralizada)

Cómo mantener un **staging** que es una copia fiel de producción pero
**neutralizada**: sin correos a clientes, sin crons, sin pagos ni bancos reales.

Basado en la [neutralización de base de datos de Odoo 19](https://www.odoo.com/documentation/19.0/administration/neutralized_database.html).

---

## 1. Qué es "neutralizar" y qué NO es

Al neutralizar, Odoo desactiva todo lo que tocaría el mundo real:

- Correos salientes (servidores de correo) y **acciones planificadas** (crons).
- Proveedores de **pago** y métodos de **envío**.
- **Sincronización bancaria** y **tokens IAP** (SMS, OCR…).
- Indexación en buscadores del website.
- Muestra un **banner rojo** permanente.

**Neutralizar NO es anonimizar.** Los emails y datos reales de clientes siguen
en la copia; simplemente no se les contacta. Si staging lo verán personas que
no deben acceder a esos datos, usa `--anonymize` (ver abajo).

---

## 2. Cómo se despliega staging

Staging es **el mismo repositorio y la misma imagen**, desplegado como un
**segundo servicio/proyecto en Dokploy**, cambiando solo variables de entorno:

| Variable | Producción | Staging |
|---|---|---|
| `ENV_NAME` | `prod` | `staging` |
| `DOMAIN` (y dominio en Dokploy) | `erp.tudominio.com` | `staging.tudominio.com` |
| `DB_NAME` | `importadora_sucre` | `importadora_staging` |
| `SKIP_DB_INIT` | *(vacío)* | **`1`** — no inicializar, se restaura |
| `ODOO_WORKERS` | `3` | `2` |
| `ODOO_MEM_LIMIT` / `ODOO_CPUS` | `4g` / `3` | `2g` / `1.5` |

La lista completa está en [`env.example`](../env.example).

`SKIP_DB_INIT=1` es imprescindible: evita que el `entrypoint.sh` intente crear
una base vacía en vez de usar la que restaura el script de refresco.

`odoo.conf` es **idéntico** en las ramas `staging` y `main`: no lleva nombre de
base ni `dbfilter`. Ambos salen de `DB_NAME` (el `dbfilter` se deriva solo como
`^<DB_NAME>$`). Si las dos ramas difieren en un archivo de configuración, es un
error: al promover `staging` a `main` producción heredaría valores de staging.

Staging lleva menos workers y un techo de memoria y CPU más bajo porque comparte
servidor con producción: una prueba pesada no debe dejarla sin recursos.

> **Regla de oro:** staging **nunca** sirve datos de producción sin neutralizar.
> El comando de abajo garantiza el orden.

---

## 3. Refrescar staging desde producción

Comando: `odoo-refresh-staging` (fuente en
[`ops/bin/odoo-refresh-staging`](../ops/bin/odoo-refresh-staging)). Es el
equivalente al **Rebuild** de un staging en Odoo.sh.

Se ejecuta **dentro del contenedor de Odoo de staging**:

```bash
docker compose exec odoo odoo-refresh-staging
```

Baja el último backup de producción de R2, lo carga neutralizado y sustituye
con él la base de staging. Pide escribir el nombre del entorno para confirmar.

### Cuándo se usa

**A demanda**, cuando se quieren datos frescos para probar. **No** en cada
despliegue: desplegar código y refrescar datos son cosas distintas.

| Acción | Efecto sobre la base de staging |
|---|---|
| Desplegar (push a `staging`) | Se conserva. Solo se actualizan los módulos cuya versión subió |
| `odoo-refresh-staging` | Se sustituye por una copia nueva de producción |

Refrescar en cada despliegue borraría las pruebas en curso y, si algo fallara
después, no se sabría si fue por el código nuevo o por los datos nuevos.

### Qué hace, en orden

1. Baja el `.zip` más reciente de `<bucket>/prod/daily/` y comprueba que es un
   backup de Odoo válido.
2. Lo carga en una base **temporal** (`<base>_refresh`), neutralizándola en la
   misma operación (`odoo-bin db load --neutralize`).
3. Comprueba que quedó neutralizada y fija `web.base.url` al dominio de
   staging, congelada.
4. Solo entonces la pone en el lugar de la base de staging
   (`odoo-bin db rename --force`), con su filestore.
5. Reinicia el contenedor. Al arrancar, se actualizan los módulos cuya versión
   en la imagen de staging sea mayor que la que traía la copia.

**Por qué una base temporal.** Odoo solo sirve la base de `DB_NAME`, así que
mientras la copia se carga y se neutraliza es invisible para los usuarios y
para los crons. Si la neutralización fallara, la copia nunca llega a ponerse en
servicio. Cargar directamente sobre el nombre definitivo dejaría un intervalo
con datos de producción activos y sin neutralizar.

**Por qué desde un backup y no desde producción en vivo.** No le añade carga a
producción y, de paso, cada refresco demuestra que el backup se puede
restaurar.

### Seguridad

- El comando **se niega a ejecutarse** si `ENV_NAME` no está definido o si
  parece producción (`prod`, `production`, `live`...).
- Si algo falla antes del paso 4, la base de staging actual queda intacta.
- La copia recibe un identificador de base nuevo: Odoo no la confunde con
  producción.
- En staging, el token de R2 debe ser de **solo lectura**. Le basta para bajar
  la copia y no puede borrar ni pisar los backups de producción.

### Opciones

```bash
odoo-refresh-staging                 # último backup de producción en R2
odoo-refresh-staging FICHERO.zip     # un backup concreto
odoo-refresh-staging -y              # sin pedir confirmación
odoo-refresh-staging --no-restart    # no reiniciar al terminar
```

Sin terminal interactiva (`docker exec` sin `-it`, o una tarea programada) hay
que pasar `-y`: no hay dónde escribir la confirmación.

### Programarlo (opcional)

Para tener staging al día sin intervención, una tarea en Dokploy sobre el
servicio de Odoo de **staging**:

| Campo | Valor |
|---|---|
| Service | `odoo` |
| Schedule | `0 9 * * 1` (lunes, 04:00 en Ecuador) |
| Command | `odoo-refresh-staging -y` |

Avisar al equipo: lo que hubiera en staging se pierde en cada refresco.

### Si falla

| Mensaje | Qué pasó | Qué hacer |
|---|---|---|
| `Refresco ABORTADO. La base ... no se ha tocado` | Falló antes del cambio | Corregir la causa y repetir. Staging sigue como estaba |
| `No se pudo sustituir ... tras 3 intentos` | Otra sesión tiene abierta la base (alguien con `psql`, un backup en curso) | Cerrar esa sesión y repetir |
| `Refresco INCOMPLETO` | La base vieja ya se borró y el renombrado falló | La copia nueva, ya neutralizada, sigue en `<base>_refresh`. El propio mensaje indica el comando para terminar |

### Mientras producción siga en el proyecto antiguo

El proyecto antiguo no genera backups con `odoo-backup`, así que no hay nada en
`prod/daily/` que bajar. El backup se saca a mano de la producción antigua, con
el mismo comando nativo, y se le pasa como fichero:

```bash
# 1. Volcar la producción antigua (solo lectura) dentro de su contenedor.
#    HOST, PORT, USER y PASSWORD son variables de ese contenedor.
docker exec <odoo-produccion-antigua> sh -c \
  'python3 /opt/odoo/odoo-bin db -c /etc/odoo/odoo.conf --db_host "$HOST" --db_port "${PORT:-5432}" -r "$USER" -w "$PASSWORD" dump importadora_sucre /tmp/prod.zip'

# 2. Llevarlo al contenedor de staging.
docker cp <odoo-produccion-antigua>:/tmp/prod.zip /tmp/prod.zip
docker cp /tmp/prod.zip <odoo-staging>:/home/odoo/backups/prod.zip

# 3. Refrescar staging con ese fichero.
docker exec -it <odoo-staging> odoo-refresh-staging /home/odoo/backups/prod.zip
```

Es el mismo camino que servirá para el traslado definitivo de producción, con
`odoo-bin db load --force --move` en lugar del refresco (ver
[backups.md](backups.md), sección 5).

### Lo que este comando no hace

No **anonimiza**. Neutralizar impide contactar a los clientes, pero sus datos
siguen en la copia. Si staging lo van a ver personas que no deben acceder a
ellos, hay que ofuscarlos aparte.

---

## 4. Correo en staging (opcional pero recomendable)

La neutralización **desactiva** el correo saliente, así que por defecto no sale
nada. Si quieres **ver** los correos de prueba, apunta el servidor de correo
saliente de staging a un **MailHog** (o similar) en vez de dejarlo apagado.
Nunca configures un SMTP real en staging.

---

## 5. Nota sobre versiones

Tras un refresco, el contenedor se reinicia y `entrypoint.sh` actualiza solo los
módulos **cuya versión en la imagen de staging es mayor** que la de la copia.
Eso cubre el caso normal: staging lleva código más nuevo que producción en los
módulos propios.

No cubre un **cambio del fuente de Odoo**. Si la imagen de staging trae una
compilación de Odoo distinta de la de producción, los módulos de Odoo no suben
de versión y la comparación no los detecta. En ese caso, tras el refresco hay
que desplegar una vez con `UPGRADE=all` y volver a vaciar la variable (ver
[despliegue-dokploy.md](despliegue-dokploy.md), sección 10).
