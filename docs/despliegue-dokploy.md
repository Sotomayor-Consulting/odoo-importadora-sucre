# Despliegue en Dokploy — Odoo 19 Enterprise

Documento de referencia para operar y mantener el despliegue.
Ultima verificacion: 2 de septiembre de 2026.

Para levantar el stack en tu maquina antes de desplegar, ver
[pruebas-locales.md](pruebas-locales.md).

---

## 1. Arquitectura

El repositorio **no contiene el codigo fuente de Odoo**. Solo lleva lo que
cambia a menudo:

```
custom_addons/      modulos propios de este cliente
shared/             modulos compartidos de Sotomayor Consulting (submodulo de git,
                    repo odoo-sci-shared-addons, rama 19.0)
docs/               esta documentacion
.dockerignore       Docker NO respeta .gitignore: sin esto el contexto de
                    build pasaria de 2 MB a 410 MB
Dockerfile          construye la imagen, descarga el fuente desde R2
docker-compose.yml  servicios odoo + postgres
odoo.conf           configuracion comun a todos los entornos (sin credenciales)
env.example         plantilla de variables: lo que cambia por entorno
```

Dentro de la imagen, la estructura es **la misma que Odoo.sh**:

```
/home/odoo/
  .config/odoo/odoo.conf   configuracion comun (lo demas llega por entorno)
  src/odoo/                fuente de Odoo (Community + Enterprise, un tarball)
  src/user/                este repositorio, con sus mismos nombres:
    custom_addons/           modulos propios del cliente
    shared/                  submodulo odoo-sci-shared-addons
  data/                    data_dir: filestore y sesiones (volumen odoo-data)
```

Dos diferencias deliberadas con Odoo.sh: no hay `src/enterprise/` (el tarball
de odoo.com ya trae Community y Enterprise juntos) ni `logs/` (en Docker los
logs van a la salida estandar y se ven en Dokploy).

**Permisos.** El codigo y la configuracion son de `root` y de solo lectura para
el proceso de Odoo, que corre como el usuario `odoo`. Ese usuario solo puede
escribir en `data/` y en sus caches (`.cache/`, `.local/`). Un fallo que permita
ejecutar codigo dentro de Odoo no puede reescribir el fuente. Consecuencia
practica: **no se parchea codigo dentro de un contenedor en marcha**; cualquier
cambio pasa por el repositorio y un despliegue.

`odoo-bin` esta en el `PATH`, y `docker compose exec` hereda la configuracion
del contenedor:

```bash
docker compose exec odoo odoo-bin shell
```

El fuente (`odoo_19.0+e.20260902.tar.gz`, ~427 MB) vive en un bucket **privado**
de Cloudflare R2 y se descarga durante el build.

**Por que asi.** El tarball descomprimido son 2 GB en 92.691 archivos. Si
estuviera versionado, Dokploy lo clonaria en cada despliegue. Ademas contiene
codigo con licencia OEEL-1, que no debe quedar en un repositorio git.

**Por que el fuente completo y no solo los modulos enterprise.** Se midio la
alternativa de partir de la imagen oficial de Odoo y añadirle solo los modulos
enterprise: esa imagen traia el nightly `20260817` y el tarball el `20260901` —
15 dias y 23 modulos de diferencia. Mezclar dos nightlies produce fallos que no
aparecen al desplegar, sino semanas despues y sin error claro. Un unico origen
elimina esa categoria entera de problemas.

**Por que no se usa la imagen oficial de Odoo.** La imagen se construye desde
`ubuntu:noble` (24.04), que es la distribucion a cuyas versiones esta pinneado
el `requirements.txt` de Odoo. Las dependencias se instalan siguiendo la
documentacion oficial de instalacion desde fuente: paquetes `python3-*` de la
distribucion, `pip install -r requirements.txt` como red de seguridad,
`wkhtmltopdf 0.12.6.1-3` con Qt parcheado (verificado por SHA1) y `rtlcss` por
npm para los idiomas RTL.

Ventaja medida: la imagen baja de **5.9 GB a 4.19 GB**. Partiendo de la imagen
oficial habia que borrar su Odoo para evitar la fusion de namespaces, pero ese
borrado no recupera espacio: los archivos siguen en la capa base.

El precio es mantener la lista de dependencias del sistema. `entrypoint.sh` es
propio y minimo: valida que las variables obligatorias existan, espera a
Postgres, inicializa la base la primera vez y arranca el servidor. No construye
configuracion: Odoo 19 la lee sola del entorno (ver seccion 2).

---

## 1.bis Modulos compartidos (submodulo `shared/`)

`shared/` no es una carpeta normal: es un **submodulo de git** que apunta a un
commit concreto del repo `odoo-sci-shared-addons` (rama `19.0`). Este repo solo
guarda ese puntero, no el codigo.

**Clonar.** Un `git clone` normal deja `shared/` vacio:

```bash
git clone --recurse-submodules git@github.com:Sotomayor-Consulting/odoo-importadora-sucre.git
# o, en un clon ya hecho:
git submodule update --init
```

**Dokploy.** En la configuracion del proveedor git del servicio hay que activar
la opcion de **submodulos**, y la credencial (GitHub App o deploy key) necesita
lectura sobre los DOS repos. Si falta, el build falla con
`FATAL: shared/ esta vacio` (red de seguridad del Dockerfile).

La URL en `.gitmodules` es relativa (`../odoo-sci-shared-addons.git`): hereda el
protocolo del repo padre, asi que sirve igual por SSH que por HTTPS.

**Actualizar los modulos compartidos.** Nunca se editan aqui dentro. El cambio
se hace en `odoo-sci-shared-addons` y aqui se sube el puntero, por PR a
`staging`:

```bash
git -C shared fetch origin && git -C shared checkout origin/19.0
git add shared && git commit -m "chore(shared): subir puntero a <commit>"
```

Asi una mejora hecha para otro cliente no llega a este hasta que alguien lo
decide y lo prueba en staging. Si el cambio trae version nueva de un modulo,
hay que actualizarlo en el despliegue (ver seccion 10).

---

## 2. Variables de entorno en Dokploy

**Regla:** el repositorio y la imagen son identicos en staging y produccion.
Lo unico que distingue un entorno de otro son sus variables en Dokploy. Las
ramas `staging` y `main` no deben diferir en ningun archivo de configuracion.

`odoo.conf` lleva solo lo comun (rutas, `proxy_mode`, `list_db`). El resto
llega por variables que **Odoo 19 lee de forma nativa**:

- `PGHOST`, `PGPORT`, `PGUSER`, `PGPASSWORD`, `PGDATABASE`: conexion y base.
- `ODOO_<OPCION>`: cualquier otra opcion (`ODOO_WORKERS`, `ODOO_DBFILTER`...).

Precedencia: linea de comandos > entorno > `odoo.conf` > valor por defecto.
`docker-compose.yml` traduce las variables de Dokploy a esos nombres.

La lista completa, con los valores de cada entorno, esta en
[`env.example`](../env.example). Las que no tienen valor por defecto y hacen
fallar el despliegue si faltan:

| Variable | Produccion | Staging | Uso |
|---|---|---|---|
| `ENV_NAME` | `prod` | `staging` | Nombre unico del entorno (router de Traefik) |
| `DOMAIN` | `erp.tudominio.com` | `staging.tudominio.com` | Dominio publico |
| `DB_NAME` | `importadora_sucre` | `importadora_staging` | Base que sirve el stack |
| `ODOO_DB_USER` / `ODOO_DB_PASSWORD` | *(propias)* | *(propias)* | Rol de aplicacion |
| `ADMIN_PASSWD` | *(propia)* | *(propia)* | Master password de Odoo |
| `POSTGRES_USER` / `POSTGRES_PASSWORD` | *(propias)* | *(propias)* | Superusuario de Postgres |
| `R2_URL` | URL prefirmada | URL prefirmada | Descarga del fuente en el build |

Las de dimensionamiento (`ODOO_WORKERS`, `ODOO_LIMIT_MEMORY_*`,
`ODOO_MEM_LIMIT`, `ODOO_CPUS`) tienen por defecto los valores de **staging**.
En produccion hay que definirlas explicitamente; la tabla esta en `env.example`.

Como `docker compose exec` hereda el entorno del contenedor, cualquier comando
de Odoo lanzado asi usa la misma configuracion sin pasar argumentos:

```bash
docker compose exec odoo odoo-bin shell
```

`R2_URL` se entrega al build como **secreto de BuildKit**, no como `ARG`.
Verificado: no aparece en `docker history` ni en ninguna capa de la imagen.
Verificado tambien que Compose la resuelve desde el archivo `.env` que genera
Dokploy, sin necesidad de exportarla.

Generar la URL prefirmada:

```bash
aws s3 presign s3://TU_BUCKET/odoo_19.0+e.20260902.tar.gz \
  --endpoint-url https://TU_ACCOUNT_ID.r2.cloudflarestorage.com \
  --expires-in 604800
```

> **Nunca** imprimas el secreto dentro de un `RUN` (`echo`, `cat`): apareceria
> en los logs de build de Dokploy.

---

## 2.bis Redes

El stack usa dos redes, y la separacion es deliberada:

| Red | Quien la crea | Quien la usa |
|---|---|---|
| `internal` | Compose | `odoo` y `db` |
| `dokploy-network` | **Dokploy** (externa) | solo `odoo` |

`dokploy-network` esta declarada como `external: true`: Compose **no** la crea y
falla el `up` si no existe. En el servidor la crea Dokploy para su proxy. En
local hay que crearla a mano:

```bash
docker network create dokploy-network
```

**La base de datos no esta en la red compartida.** Solo `odoo` la alcanza, y
solo `odoo` es alcanzable por el proxy. Postgres nunca queda expuesto a los
demas servicios que Dokploy tenga en ese host.

Nota: `docker compose config` **no** detecta que la red externa falte; el error
aparece al hacer `up`.

---

## 3. Despliegue automatico

`git push` → webhook de Dokploy → `docker compose build` → despliegue.

No hay que descargar ni subir nada a mano. El fuente lo obtiene el build
desde R2.

**La capa de descarga se cachea.** Los redespliegues normales (cambios en
`custom_addons` o en la configuracion) reutilizan la capa y **no** vuelven a
descargar de R2: tardan segundos.

---

## 4. La trampa de la cache — leer antes de actualizar Odoo

Como la capa de descarga se cachea, **subir un tarball nuevo a R2 no basta**:
Docker reutilizaria la capa antigua y seguirias corriendo el fuente viejo, sin
ningun aviso.

El `ARG ODOO_VERSION` del `Dockerfile` existe para esto: forma parte del
comando `RUN`, asi que cambiarlo invalida la cache y fuerza la descarga.

---

## 5. Ritual de actualizacion de Odoo

Tres o cuatro veces al año:

1. Descargar el tarball nuevo desde tu cuenta de odoo.com.
2. `sha256sum odoo_19.0+e.AAAAMMDD.tar.gz` y anotar el resultado.
3. Subirlo al bucket privado de R2.
4. Generar una `R2_URL` prefirmada nueva y actualizarla en Dokploy.
5. En el `Dockerfile`, actualizar `ODOO_VERSION` y `ODOO_SHA256`.
6. Commit y push. Dokploy reconstruye y despliega.

Si algo falla, se vuelve al commit anterior: el `Dockerfile` describe por
completo la version que corre.

---

## 6. Caducidad de la URL prefirmada

Las URL prefirmadas de S3/R2 caducan como maximo a los **7 dias**.

En el dia a dia da igual, porque los redespliegues usan la cache. Pero un build
**sin cache** con la URL caducada falla. Ocurre al cambiar `ODOO_VERSION`, al
migrar a un servidor nuevo, o si se purga la cache de Docker.

Regla practica: **refrescar `R2_URL` es el paso previo a cualquier
reconstruccion completa.**

Si esto llega a molestar, la alternativa es servir el archivo desde un endpoint
con token estatico (Cloudflare Worker o Access) en lugar de una URL prefirmada.

---

## 7. Hechos verificados

> Estas comprobaciones se hicieron con la imagen de septiembre de 2026, cuando
> el fuente estaba en `/opt/odoo` y los addons en `/mnt`. Las rutas de esta
> seccion son las de entonces; las vigentes estan en la seccion 1.

Comprobados sobre la instalacion real, no deducidos de la documentacion:

- **El tarball no trae `odoo-bin`** (es una distribucion sdist). Se arranca con
  `python3 -m odoo`. Cualquier receta que invoque `./odoo-bin` falla.
- **`odoo` es un namespace package** (sin `__init__.py`). Importa al construir
  sobre una base que ya tenga Odoo instalado: los dos arboles se fusionarian en
  `sys.path` **sin ningun error visible**. Partiendo de `ubuntu:noble` el
  problema no existe, porque no hay ningun Odoo previo.
- **Un `addons_path` cuyo directorio no contenga ningun modulo se descarta**
  con el aviso `invalid addons directory`. Es lo que ocurre mientras
  `custom_addons/` solo tenga el `.gitkeep`: es normal y desaparece solo al
  añadir el primer modulo. Verificado: con un modulo real, la ruta aparece en
  `addons paths`.
- La imagen corre como `odoo` con **uid 100 / gid 101**, los mismos que usa la
  imagen oficial, para que los volumenes existentes sigan siendo compatibles.
  De ahi los `--chown` en los `COPY`.
- Imagen resultante: **4.19 GB**. Build completo: ~3 minutos.
- Instalacion verificada de un modulo enterprise (`web_enterprise`, OEEL-1) y
  de uno propio desde `/mnt/custom_addons`, con 1476 modulos en el catalogo.

---

## 8. Puntos abiertos

- **Facturacion electronica (SRI) y ATS.** `l10n_ec_edi`, `l10n_ec_reports` y
  `l10n_ec_reports_ats` son modulos Enterprise (OPL-1) y requieren suscripcion
  activa. `l10n_ec` (plan de cuentas) si es community. Confirmar la cobertura
  legal antes de entrar en produccion.
- **Soporte de `--secret` en Dokploy.** El mecanismo esta verificado con
  `docker compose build` local. Conviene confirmarlo en el primer despliegue
  real y revisar que la URL no aparezca en los logs de build.
- **Websockets.** El puerto 8072 esta expuesto; comprobar que el proxy de
  Dokploy lo enruta para que el chat y las notificaciones en vivo funcionen.
- **Copias de seguridad.** Definir respaldo del volumen `db-data` (base) y
  `odoo-data` (filestore con los adjuntos). Ambos son imprescindibles.

---

## 9. Websocket detras del proxy (chat y notificaciones en vivo)

La [doc oficial de Odoo](https://www.odoo.com/documentation/19.0/administration/on_premise/deploy.html)
exige dos cosas para que el chat y las notificaciones en vivo funcionen tras un
proxy:

1. Correr Odoo con `--proxy-mode` (ya esta: `proxy_mode = True` en `odoo.conf`).
2. Que el proxy **redirija las peticiones cuyo path empieza por `/websocket` al
   puerto gevent 8072**; el resto va al 8069.

Ademas, ese puerto 8072 **solo existe si `workers > 0`** (ya esta: `workers = 5`).

**Como se hace en Dokploy (Traefik).** El dominio principal (8069) se configura
por la UI de Dokploy como siempre. La ruta del websocket la añade el bloque
`labels` del servicio `odoo` en `docker-compose.yml`: crea un router
`importadora-<ENV_NAME>-ws` con `PathPrefix(/websocket)` y prioridad alta que apunta al puerto
8072. Traefik gestiona solo el *upgrade* de websocket y las cabeceras
`X-Forwarded-*`, asi que no hace falta middleware extra.

Ajustes a revisar en ese bloque para que encajen con tu Dokploy:
- `DOMAIN` debe ser el mismo dominio que pusiste en la UI.
- `entrypoints=websecure` y `tls.certresolver=letsencrypt` son los nombres por
  defecto de Dokploy; cambialos si tu instalacion usa otros.

**Comprobacion.** Con el stack arriba, entra a Odoo y abre Discuss o envia un
mensaje: debe llegar en vivo sin recargar. En las herramientas de desarrollador
del navegador, la peticion a `wss://TU_DOMINIO/websocket` debe quedar en estado
`101 Switching Protocols`.

---

## 10. Actualizacion de modulos (variable UPGRADE)

El `entrypoint.sh` inicializa la base la primera vez, pero **no actualiza los
modulos por si solo**: subir una version nueva del fuente o cambiar un modulo no
aplica sus migraciones hasta que se corre `-u`.

Para eso esta la variable `UPGRADE`:

- **Operacion normal:** `UPGRADE` vacio. Los arranques no actualizan nada (es
  lento y no debe correr en cada boot).
- **Despliegue de actualizacion:** pon `UPGRADE=all` en Dokploy, despliega (el
  entrypoint corre `-u all --stop-after-init` antes de arrancar los workers,
  aplicando las migraciones) y **vuelve a vaciar `UPGRADE`** para el siguiente
  despliegue. Para un cambio acotado, `UPGRADE=nombre_del_modulo`.

Encaja en el "Ritual de actualizacion de Odoo" (seccion 5): tras subir el
tarball nuevo y cambiar `ODOO_VERSION`/`ODOO_SHA256`, haz **un** despliegue con
`UPGRADE=all`, verifica, y limpia la variable.

> Antes de un `UPGRADE=all` en produccion, ten un backup reciente (ver
> [backups.md](backups.md)) y, si puedes, pruebalo primero en staging (ver
> [entornos-staging.md](entornos-staging.md)).
