# Pruebas locales con Docker

Como levantar el stack en tu maquina antes de desplegar en Dokploy.
Procedimiento ejecutado y verificado el 2 de septiembre de 2026 sobre
Debian WSL2 con Docker 29.6.2.

Ver [despliegue-dokploy.md](despliegue-dokploy.md) para la arquitectura.

---

## 1. Requisitos

- Docker con BuildKit (por defecto desde Docker 23).
- ~10 GB libres: la imagen ocupa ~5.9 GB y el build necesita margen.
- Acceso al tarball de Odoo: por URL prefirmada de R2, o el archivo en local.

> **No instales Dokploy en WSL para esto.** Activa Docker Swarm y se adueña
> del host, ademas de que la IP de WSL cambia en cada reinicio. Para probar en
> local basta `docker compose`; Dokploy va en el VPS.

---

## 2. Configurar el entorno

```bash
cp env.example .env
```

Edita `.env` con tus valores:

```
POSTGRES_USER=odoo
POSTGRES_PASSWORD=una_clave_larga
R2_URL=https://...url-prefirmada-de-r2...
```

`.env` esta en `.gitignore`. No lo commitees.

Generar la URL prefirmada:

```bash
aws s3 presign s3://TU_BUCKET/odoo_19.0+e.20260902.tar.gz --endpoint-url https://TU_ACCOUNT_ID.r2.cloudflarestorage.com --expires-in 3600
```

---

## 3. Opcion sin red: servir el tarball desde tu maquina

Util si no quieres gastar transferencia de R2 o trabajas sin conexion.

Sirve el archivo:

```bash
python3 -m http.server 8899 --bind 127.0.0.1
```

El contenedor de build **no alcanza el `127.0.0.1` del host** por defecto: hay
que darle red del host. Como Compose carga `docker-compose.override.yml`
automaticamente, se hace ahi sin tocar el archivo de produccion:

```yaml
services:
  odoo:
    build:
      network: host
```

Y en `.env`:

```
R2_URL=http://127.0.0.1:8899/odoo_19.0%2Be.20260902.tar.gz
```

> El `+` del nombre debe ir como `%2B` en la URL.

`docker-compose.override.yml` esta en `.gitignore` a proposito: si se
versionara, Dokploy lo fusionaria en produccion y desplegaria con red del host.

---

## 4. Construir y levantar

```bash
docker compose up --build -d
```

El primer build tarda unos 3 minutos: instala las dependencias de sistema,
`wkhtmltopdf`, resuelve `requirements.txt` y extrae los 2 GB del tarball.
Los siguientes son casi instantaneos: las capas se cachean.

Ver el arranque:

```bash
docker compose logs -f odoo
```

Señales de que va bien:

```
odoo: Odoo version 19.0+e-20260902
odoo: addons paths: _NamespacePath(['/opt/odoo/odoo/addons', ...])
odoo: database: odoo@db:5432
odoo.service.server: HTTP service (werkzeug) running on ...:8069
```

Odoo queda en <http://localhost:8069>. Para publicarlo hay que añadir
`ports: ["8069:8069"]` en el override: el `docker-compose.yml` de produccion
solo usa `expose`, porque alli enruta el proxy de Dokploy.

---

## 5. Crear una base de datos de prueba

Sin datos de demostracion:

```bash
docker compose exec -T odoo python3 -m odoo -c /etc/odoo/odoo.conf -d test -i base --stop-after-init --without-demo=all --db_host=db --db_user=odoo --db_password=TU_CLAVE
```

`docker compose exec` no pasa por el entrypoint, asi que hay que dar los
`--db_*` a mano. En el arranque normal los inyecta `entrypoint.sh` desde las
variables `HOST`, `PORT`, `USER` y `PASSWORD`.

Para instalar un modulo concreto, cambia `-i base` por el que quieras
(`-i web_enterprise`, `-i l10n_ec`, ...). Verificado con `web_enterprise`
y con un modulo propio en `/mnt/custom_addons`..

---

## 6. Verificaciones

Que corre el fuente correcto y no el de la imagen oficial:

```bash
docker compose exec -T odoo python3 -c "import odoo.cli, odoo.release; print(odoo.cli.__file__); print(odoo.release.version)"
```

Debe responder `/opt/odoo/odoo/cli/__init__.py`. Si dijera
`/usr/lib/python3/dist-packages/...`, el `rm -rf` del Dockerfile no surtio
efecto y estarias corriendo una mezcla de dos versiones.

Catalogo de modulos visible (deben ser 1476):

```bash
docker compose exec -T odoo bash -lc "ls /opt/odoo/odoo/addons | wc -l"
```

Estado de los modulos en la base:

```bash
docker compose exec -T db psql -U odoo -d test -tAc "select state, count(*) from ir_module_module group by state;"
```

Que la HTTP responde:

```bash
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8069/web/database/selector
```

**Que la URL de R2 no quedo grabada en la imagen** (debe devolver 0):

```bash
docker history --no-trunc $(docker compose images -q odoo) | grep -c r2.cloudflarestorage.com
```

---

## 7. Problemas frecuentes

**El build falla en el `curl` con exit 2.** No hay red hacia el origen. Si
sirves el archivo en local, falta `network: host` en el override. Si usas R2,
la URL prefirmada caduco (maximo 7 dias): genera una nueva.

**El build falla con `sha256sum: WARNING: 1 computed checksum did NOT match`.**
El `ARG ODOO_SHA256` del Dockerfile no corresponde al tarball descargado.
Recalculalo con `sha256sum` y actualizalo. La comprobacion es intencional: es
lo que impide construir con un archivo corrupto o distinto del archivado.

**Cambiaste el tarball en R2 y sigue arrancando la version vieja.** La capa de
descarga esta cacheada. Cambia `ARG ODOO_VERSION` en el Dockerfile, o fuerza
`docker compose build --no-cache`.

**Copiar el fuente descomprimido a WSL tarda horas.** El sistema de archivos
9p de WSL colapsa con los 92.691 archivos del tarball. Trabaja siempre con el
`.tar.gz`: son 427 MB en un solo archivo y se copia en segundos.

**Odoo avisa `invalid addons directory '/mnt/custom_addons'` y lo descarta.**
Es **normal mientras no tengas modulos propios**: Odoo exige que un
`addons_path` contenga al menos un subdirectorio con `__init__.py` y
`__manifest__.py`, y si no lo descarta. No es un problema de permisos ni del
Dockerfile. En cuanto añadas tu primer modulo, la ruta aparece en
`addons paths` y el aviso desaparece.

Si el mensaje fuera `no such directory`, entonces si falta el directorio en el
contexto de build: debe existir aunque este vacio (por eso lleva `.gitkeep`).

---

## 8. Limpieza

Parar y borrar contenedores y volumenes de la prueba:

```bash
docker compose down -v
```

Borrar la imagen construida:

```bash
docker rmi $(docker compose images -q odoo)
```

La cache de build de Odoo ocupa varios GB. Para recuperarla:

```bash
docker builder prune -a -f
```
