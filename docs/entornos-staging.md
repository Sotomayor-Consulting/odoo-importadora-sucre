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
| `DB_NAME` | `importadora_sucre` | `importadora_staging` |
| `SKIP_DB_INIT` | *(vacío)* | **`1`** — no inicializar, se restaura |
| Dominio (Dokploy) | `erp.tudominio.com` | `staging.tudominio.com` |

`SKIP_DB_INIT=1` es imprescindible: evita que el `entrypoint.sh` intente crear
una base vacía en vez de usar la que restaura el script de refresco.

En `odoo.conf`, staging necesita su propio `db_name`/`dbfilter`. Si prefieres no
mantener dos `odoo.conf`, deja el filtro por host (`dbfilter = ^%d$`) o
sobreescribe `db_name`/`dbfilter` por variable de entorno en Dokploy.

> **Regla de oro:** la base de staging **nunca** en la red del proxy antes de
> estar neutralizada. El script de abajo garantiza el orden.

---

## 3. Refrescar staging desde producción

Script: [`scripts/refresh-staging.sh`](../scripts/refresh-staging.sh).

Se ejecuta **en el host** donde corren ambos stacks (necesita `docker`).

### Preparación (una vez)

```bash
cp scripts/refresh-staging.env.example scripts/refresh-staging.env
# Edita scripts/refresh-staging.env con los nombres de contenedor y credenciales.
# Ver los contenedores:  docker ps --format '{{.Names}}'
```

`scripts/refresh-staging.env` está en `.gitignore`: **no se versiona**.

### Ejecutar

```bash
./scripts/refresh-staging.sh              # interactivo, pide confirmacion
./scripts/refresh-staging.sh -y           # sin preguntar (cron/CI)
./scripts/refresh-staging.sh --anonymize  # ademas ofusca emails/telefonos/logins
```

### Qué hace, en orden

1. `pg_dump` de producción (**solo lectura** sobre prod).
2. Copia del **filestore** de producción (adjuntos).
3. Para el Odoo de staging y **recrea** su base desde el dump.
4. Restaura el filestore en staging.
5. **Neutraliza** la base de staging con el Odoo **parado** (así staging nunca
   sirve datos de producción sin neutralizar). Corre los `neutralize.sql` de
   todos los módulos, incluidos los de `custom_addons`.
6. Fija `web.base.url` al dominio de staging y lo **congela**.
7. *(Opcional)* Ofusca datos personales.
8. Arranca el Odoo de staging.

El script **aborta** si el destino coincidiera con producción (base o
contenedor), y limpia sus temporales al terminar.

---

## 4. Correo en staging (opcional pero recomendable)

La neutralización **desactiva** el correo saliente, así que por defecto no sale
nada. Si quieres **ver** los correos de prueba, apunta el servidor de correo
saliente de staging a un **MailHog** (o similar) en vez de dejarlo apagado.
Nunca configures un SMTP real en staging.

---

## 5. Nota sobre versiones

El script restaura la base tal cual está en producción. Si la imagen de Odoo de
staging es de una **versión distinta** a la de producción, tras el refresco hay
que correr una actualización de módulos (`-u all`) antes de usar staging. Si
ambas corren la misma versión (lo normal), no hace falta.
