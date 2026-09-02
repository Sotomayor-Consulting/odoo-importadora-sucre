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
custom_addons/      modulos propios
docs/               esta documentacion
Dockerfile          construye la imagen, descarga el fuente desde R2
docker-compose.yml  servicios odoo + postgres
odoo.conf           configuracion (sin credenciales)
env.example         plantilla de variables
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
propio y replica el comportamiento del oficial: construye los argumentos de
conexion desde `HOST`, `PORT`, `USER` y `PASSWORD`, y solo los añade si no
estan ya en `odoo.conf`.

---

## 2. Variables de entorno en Dokploy

| Variable | Ejemplo | Uso |
|---|---|---|
| `POSTGRES_USER` | `odoo` | Usuario de la base |
| `POSTGRES_PASSWORD` | *(clave larga)* | Contraseña de la base |
| `R2_URL` | URL prefirmada de R2 | Descarga del fuente en el build |

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
