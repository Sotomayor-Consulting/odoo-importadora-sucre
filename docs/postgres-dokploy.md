# PostgreSQL como servicio de Dokploy

La base de datos **no** forma parte del `docker-compose.yml` de Odoo. Es un
servicio aparte, creado en Dokploy como base de datos nativa, dentro del mismo
proyecto. Es el mismo reparto que en Odoo.sh, donde la base es un servidor
distinto del que ejecuta Odoo.

**Por que.** Un despliegue de Odoo es rutina; tocar la base debe ser un acto
deliberado. Separadas, redesplegar Odoo nunca recrea el contenedor de la base, y
esta tiene sus propios limites de recursos, sus backups y su actualizacion de
version.

> Los nombres de las pantallas de Dokploy citados aqui pueden variar entre
> versiones. Lo que importa es el valor de cada ajuste, no el nombre del menu.

---

## 1. Un servicio por entorno

| | Staging | Produccion |
|---|---|---|
| Servicio Postgres | propio | propio |
| Imagen | `postgres:18` | `postgres:18` |
| Puerto externo | **ninguno** | **ninguno** |

Staging y produccion **no comparten servidor de base de datos**, aunque esten en
el mismo VPS. Un `dropdb` equivocado, una migracion rota o una consulta pesada
en staging no pueden alcanzar los datos de produccion.

La version mayor (18) debe coincidir con `PG_MAJOR` en el `Dockerfile`: el
cliente de la imagen de Odoo tiene que ser de la misma version que el servidor,
o `pg_dump` se niega a volcarlo.

---

## 2. Crear el servicio

En el proyecto de Dokploy, crear una base de datos PostgreSQL con:

- **Imagen:** `postgres:18`.
- **Usuario:** un nombre de administracion, por ejemplo `odoo_admin`. Este es el
  **superusuario**; se usa solo para administrar y respaldar, nunca desde Odoo.
- **Contraseña:** larga y distinta en cada entorno.
- **Puerto externo:** dejarlo **vacio**. Publicarlo expone la base a internet.

Tras desplegarlo, Dokploy muestra el **host interno** del servicio. Ese valor es
el `DB_HOST` de Odoo.

---

## 3. Crear el rol de Odoo (una sola vez por servicio)

Odoo no se conecta como superusuario. Usa un rol propio con lo minimo: poder
entrar y poder crear sus bases. Asi, un modulo defectuoso o una inyeccion SQL no
obtienen control del servidor de base de datos.

Desde la terminal del servicio Postgres en Dokploy:

```bash
psql -U odoo_admin -d postgres
```

```sql
CREATE ROLE odoo WITH LOGIN CREATEDB PASSWORD 'una_clave_larga_y_distinta';
```

Ese usuario y esa clave son `ODOO_DB_USER` y `ODOO_DB_PASSWORD` en las variables
del servicio de Odoo.

Comprobar que el rol **no** es superusuario (debe devolver `f`):

```sql
SELECT rolsuper FROM pg_roles WHERE rolname = 'odoo';
```

---

## 4. Ajustes de rendimiento

La imagen de Postgres arranca con valores pensados para que funcione en
cualquier maquina, no para Odoo: `shared_buffers` es de solo 128 MB. Los ajustes
se pasan como argumentos del comando del servicio (configuracion avanzada).

Referencia para un VPS de 4 vCPU / 8 GB que aloja los dos entornos:

| Parametro | Staging | Produccion | Para que |
|---|---|---|---|
| `shared_buffers` | `256MB` | `1GB` | Cache propia de Postgres |
| `effective_cache_size` | `768MB` | `3GB` | Estimacion de la cache total; solo orienta al planificador |
| `work_mem` | `8MB` | `16MB` | Memoria por operacion de ordenacion |
| `maintenance_work_mem` | `128MB` | `256MB` | `VACUUM`, creacion de indices, restauraciones |
| `max_connections` | `100` | `150` | Ver la regla de abajo |
| `random_page_cost` | `1.1` | `1.1` | Disco SSD |

Comando de produccion:

```
postgres -c shared_buffers=1GB -c effective_cache_size=3GB -c work_mem=16MB -c maintenance_work_mem=256MB -c max_connections=150 -c random_page_cost=1.1
```

Comando de staging:

```
postgres -c shared_buffers=256MB -c effective_cache_size=768MB -c work_mem=8MB -c maintenance_work_mem=128MB -c max_connections=100 -c random_page_cost=1.1
```

**Regla de conexiones.** Cada proceso de Odoo abre hasta `ODOO_DB_MAXCONN`
conexiones (20). Debe cumplirse:

```
(ODOO_WORKERS + 2) x ODOO_DB_MAXCONN  <  max_connections
```

Produccion: (3 + 2) x 20 = 100, por debajo de 150. Staging: (2 + 2) x 20 = 80,
por debajo de 100. El margen es para backups, la terminal y el propio Dokploy.

**Limite de memoria del servicio.** Fijarlo en Dokploy por encima de
`shared_buffers` con holgura: alrededor de 1 GB en staging y 2,5 GB en
produccion.

**Si aparece `could not resize shared memory segment`:** las consultas en
paralelo usan `/dev/shm`, que en un contenedor es de 64 MB por defecto. Se
resuelve ampliando la memoria compartida del servicio o, mas simple, añadiendo
`-c max_parallel_workers_per_gather=0` al comando.

---

## 5. Red y aislamiento

El servicio Postgres y el de Odoo se ven por `dokploy-network`, la red
compartida de Dokploy. Por esa misma red llega el proxy.

Esto es menos aislamiento que una red privada solo para Odoo y su base: en
principio, cualquier otro servicio conectado a `dokploy-network` puede intentar
abrir una conexion. Lo que protege la base es:

- **No hay puerto externo:** desde internet no se llega.
- **Contraseñas largas y distintas** por rol y por entorno.
- **Odoo usa un rol sin superusuario.**

En un VPS dedicado a este cliente es un compromiso razonable. Si el servidor
pasa a alojar aplicaciones de terceros, hay que revisarlo.

---

## 6. Backups

Al ser un servicio nativo, Dokploy puede programar backups de la base hacia un
destino S3 (Cloudflare R2) y restaurarlos desde su interfaz.

Un backup de la base **sin el filestore** no sirve para Odoo: los adjuntos
quedarian rotos. Ver [backups.md](backups.md).

---

## 7. Operar la base desde el servidor

El contenedor de una base nativa corre como servicio de Swarm y se llama
`<servicio>.1.<id aleatorio>`; el sufijo cambia en cada reinicio. Para no
depender de el, `scripts/backup.sh` y `scripts/refresh-staging.sh` aceptan el
**nombre del servicio** y localizan el contenedor solos.

Ver los nombres:

```bash
docker ps --format '{{.Names}}'
```
