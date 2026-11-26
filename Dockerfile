# Imagen de Odoo 19 Enterprise construida desde cero.
# Base: ubuntu:noble (24.04), la distribucion a cuyas versiones esta pinneado
# el requirements.txt de Odoo ("The officially supported versions ... are their
# python3-* equivalent distributed in Ubuntu 24.04 and Debian 12").
FROM ubuntu:noble

ARG ODOO_VERSION=19.0+e.20261007
ARG ODOO_SHA256=164c33a398dc4fe106a0ba19c3c7822f7efcc3afaf412c786bae3d35da253da4
ARG WKHTMLTOPDF_URL=https://github.com/wkhtmltopdf/packaging/releases/download/0.12.6.1-3/wkhtmltox_0.12.6.1-3.jammy_amd64.deb
ARG WKHTMLTOPDF_SHA1=967390a759707337b46d1c02452e2bb6b2dc6d59
# Version mayor del SERVIDOR PostgreSQL (el servicio de Dokploy). El cliente de
# la imagen debe ser de la misma: pg_dump se niega a volcar un servidor mas
# nuevo que el, y 'odoo-bin db dump' usa el pg_dump de este contenedor.
ARG PG_MAJOR=18

ENV LANG=en_US.UTF-8 \
    ODOO_RC=/home/odoo/.config/odoo/odoo.conf \
    PYTHONPATH=/home/odoo/src/odoo \
    DEBIAN_FRONTEND=noninteractive \
    PIP_BREAK_SYSTEM_PACKAGES=1

# Repositorio oficial de PostgreSQL (PGDG). Ubuntu 24.04 solo trae el cliente
# 16; de aqui sale el de PG_MAJOR. Es lo mismo que hace la imagen oficial de
# Odoo. La clave se guarda aparte y el repositorio queda atado a ella
# (signed-by), sin confiar en ella para ningun otro origen.
#
# PGDG publica tambien versiones mas nuevas de paquetes que Ubuntu ya trae, y
# apt elige siempre la mas nueva. Sin acotarlo, se instalaba python3-psycopg2
# 2.9.10 de PGDG en lugar del 2.9.9 de Ubuntu; como requirements.txt de Odoo
# fija psycopg2==2.9.9, pip intentaba recompilarlo y el build fallaba por falta
# de compilador. El archivo de preferencias deja PGDG por debajo de Ubuntu
# (prioridad 100) salvo para lo que se quiere de alli: el cliente y su libpq.
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates curl \
 && install -d /usr/share/postgresql-common/pgdg \
 && curl -fsSL -o /usr/share/postgresql-common/pgdg/apt.postgresql.org.asc \
      https://www.postgresql.org/media/keys/ACCC4CF8.asc \
 && echo "deb [signed-by=/usr/share/postgresql-common/pgdg/apt.postgresql.org.asc] https://apt.postgresql.org/pub/repos/apt noble-pgdg main" \
      > /etc/apt/sources.list.d/pgdg.list \
 && printf '%s\n' \
      'Package: *' \
      'Pin: origin apt.postgresql.org' \
      'Pin-Priority: 100' \
      '' \
      "Package: postgresql-client-${PG_MAJOR} postgresql-client-common libpq5 libpq-dev" \
      'Pin: origin apt.postgresql.org' \
      'Pin-Priority: 990' \
      > /etc/apt/preferences.d/pgdg \
 && rm -rf /var/lib/apt/lists/*

# Dependencias de sistema. Los python3-* de Noble satisfacen los pines exactos
# del requirements.txt, asi que el pip posterior apenas compila nada.
#
# La doc oficial instala esto con setup/debinstall.sh, que lee la lista
# 'Depends' de debian/control. Aqui no se puede: el tarball de odoo.com no trae
# ni ese script ni debian/control. La lista de abajo es su equivalente a mano y
# hay que revisarla contra debian/control al cambiar de version de Odoo (ver
# "Ritual de actualizacion" en docs/despliegue-dokploy.md).
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl gnupg xz-utils locales rclone \
      postgresql-client-${PG_MAJOR} \
      nodejs npm node-less \
      fonts-noto fonts-noto-cjk fonts-liberation \
      fonts-inconsolata fonts-font-awesome fonts-roboto-unhinted gsfonts \
      python3 python3-pip python3-setuptools python3-wheel python3-dev \
      libldap2-dev libpq-dev libsasl2-dev libssl-dev libffi-dev \
      python3-babel python3-cbor2 python3-chardet python3-cryptography \
      python3-dateutil python3-decorator python3-docutils python3-freezegun \
      python3-geoip2 python3-gevent python3-greenlet python3-idna \
      python3-jinja2 python3-ldap python3-libsass python3-lxml \
      python3-magic python3-markupsafe python3-num2words python3-odf \
      python3-ofxparse python3-openpyxl python3-passlib python3-pdfminer \
      python3-phonenumbers python3-pil python3-polib python3-psutil \
      python3-psycopg2 python3-pypdf2 python3-openssl python3-qrcode \
      python3-renderpm python3-reportlab python3-requests python3-rjsmin \
      python3-serial python3-slugify python3-stdnum python3-tz python3-usb \
      python3-vobject python3-watchdog python3-werkzeug python3-xlrd \
      python3-xlsxwriter python3-xlwt python3-zeep \
 # Red de seguridad del punto anterior: si psycopg2 no es el de Ubuntu, que el
 # build falle aqui con un mensaje claro y no mas tarde dentro de pip.
 && { dpkg-query -W -f='${Version}' python3-psycopg2 | grep -q '^2\.9\.9-' \
      || { echo 'FATAL: python3-psycopg2 no es el 2.9.9 de Ubuntu (revisar /etc/apt/preferences.d/pgdg)'; exit 1; }; } \
 && npm install -g rtlcss \
 && sed -i "s/^# *en_US.UTF-8/en_US.UTF-8/" /etc/locale.gen && locale-gen \
 && rm -rf /var/lib/apt/lists/* /root/.npm

# wkhtmltopdf con Qt parcheado. Sin esta build concreta, las cabeceras y pies
# de los informes PDF salen rotos. Se verifica el SHA1 publicado por upstream.
RUN curl -fsSL -o /tmp/wkhtmltox.deb "${WKHTMLTOPDF_URL}" \
 && echo "${WKHTMLTOPDF_SHA1}  /tmp/wkhtmltox.deb" | sha1sum -c - \
 && apt-get update \
 && apt-get install -y --no-install-recommends /tmp/wkhtmltox.deb \
 && rm -f /tmp/wkhtmltox.deb && rm -rf /var/lib/apt/lists/* \
 # Red de seguridad: el .deb es la build de jammy (no hay build de noble). Si
 # quedara instalada la version "without patched qt", las cabeceras y pies de
 # los PDF saldrian rotos SIN ningun error. Que el build falle aqui, ruidoso,
 # en vez de generar informes defectuosos en produccion.
 && wkhtmltopdf --version | grep -q 'with patched qt' \
      || { echo 'FATAL: wkhtmltopdf no es la build patched-qt'; exit 1; }

# Estructura de directorios: la misma que Odoo.sh, para que quien conozca una
# conozca la otra.
#
#   /home/odoo/
#     .config/odoo/odoo.conf   configuracion comun (lo demas llega por entorno)
#     src/odoo/                fuente de Odoo (Community + Enterprise, un tarball)
#     src/user/                este repositorio, con sus mismos nombres:
#       custom_addons/           modulos propios del cliente
#       shared/                  submodulo odoo-sci-shared-addons
#     data/                    data_dir: filestore y sesiones (VOLUMEN)
#     backups/                 copias locales: daily/ weekly/ monthly/ (VOLUMEN)
#
# Regla de permisos: el CODIGO y la CONFIGURACION son de root y de solo lectura
# para el proceso. El usuario 'odoo' solo puede escribir en data/ (sus datos),
# en backups/ y en .cache/ y .local/ (caches de herramientas, p. ej. fontconfig
# al generar PDF). Asi, un fallo que permita ejecutar codigo dentro de Odoo no puede
# reescribir el fuente ni la configuracion.
#
# Por eso /home/odoo en si es de root: el dueño de un directorio puede renombrar
# lo que contiene aunque no sea suyo, y bastaria eso para sustituir src/.
# chmod 755 explicito: useradd lo crea 750 y, siendo de root, 'odoo' no podria
# ni entrar.
#
# UID/GID 100:101 se mantienen: son los dueños de los archivos en los volumenes
# y backups ya existentes.
RUN groupadd -g 101 odoo \
 && useradd -u 100 -g 101 -md /home/odoo -s /bin/bash odoo \
 && mkdir -p /home/odoo/.config/odoo /home/odoo/src/odoo /home/odoo/src/user \
             /home/odoo/data /home/odoo/backups /home/odoo/.cache /home/odoo/.local \
 && chown root:root /home/odoo && chmod 755 /home/odoo \
 && chown odoo:odoo /home/odoo/data /home/odoo/backups /home/odoo/.cache /home/odoo/.local

# El tarball vive en un bucket PRIVADO de Cloudflare R2. Se descarga con un
# token de R2 de solo lectura: curl firma la peticion (AWS SigV4, el protocolo
# de la API S3 que habla R2). A diferencia de una URL prefirmada, el token no
# caduca, asi que una reconstruccion sin cache no depende de regenerar nada.
#
# Las tres piezas llegan como secretos de BuildKit: no quedan en ninguna capa
# ni en "docker history". Las credenciales se pasan a curl por su entrada
# estandar (-K -), no como argumento, para que tampoco se vean en la lista de
# procesos. Nunca se imprimen: apareceria en los logs de build.
#
# --strip-components=1 descarta el directorio con fecha, dejando una ruta
# estable entre versiones. --no-same-owner: como root, tar conservaria el
# dueño grabado en el archivo; se fuerza root.
RUN --mount=type=secret,id=r2_access_key_id \
    --mount=type=secret,id=r2_secret_access_key \
    --mount=type=secret,id=r2_object_url \
    echo "Compilando Odoo ${ODOO_VERSION}" \
 && for s in r2_access_key_id r2_secret_access_key r2_object_url; do \
      [ -s "/run/secrets/$s" ] || { echo "FATAL: falta el secreto de build $s (ver env.example)"; exit 1; }; \
    done \
 && printf 'user = "%s:%s"\n' \
      "$(cat /run/secrets/r2_access_key_id)" "$(cat /run/secrets/r2_secret_access_key)" \
    | curl -fsSL -K - --aws-sigv4 "aws:amz:auto:s3" \
        "$(cat /run/secrets/r2_object_url)" -o /tmp/src.tgz \
 && echo "${ODOO_SHA256}  /tmp/src.tgz" | sha256sum -c - \
 && tar -xzf /tmp/src.tgz -C /home/odoo/src/odoo --strip-components=1 --no-same-owner \
 && rm /tmp/src.tgz

# Red de seguridad: instala lo que los paquetes de Noble no cubran. La mayoria
# ya estara satisfecha, asi que apenas descarga nada.
RUN pip3 install --no-cache-dir -r /home/odoo/src/odoo/requirements.txt

# Como el fuente es de solo lectura para 'odoo', Python no podria guardar el
# bytecode en el primer arranque y recompilaria todo en cada inicio. Se compila
# aqui, igual que hace el paquete .deb oficial al instalarse. Va ANTES de copiar
# los addons para que esta capa (la lenta) se cachee con el fuente y no se
# repita en cada cambio de un modulo. '|| true': algun archivo de plantilla o
# de test puede no compilar y no debe tumbar el build.
RUN python3 -m compileall -q -j 0 /home/odoo/src/odoo || true

# Sin --chown: quedan de root (ver la regla de permisos de arriba).
COPY --chmod=755 odoo-bin /home/odoo/src/odoo/odoo-bin
COPY custom_addons        /home/odoo/src/user/custom_addons
COPY shared               /home/odoo/src/user/shared
# Red de seguridad: 'shared' es un submodulo de git. Si quien construye no lo
# inicializo (clon sin --recurse-submodules, o Dokploy sin la opcion de
# submodulos), la carpeta llega VACIA y Odoo arrancaria sin esos modulos, sin
# ningun error. Que el build falle aqui, ruidoso.
RUN ls /home/odoo/src/user/shared/*/__manifest__.py >/dev/null 2>&1 \
      || { echo 'FATAL: shared/ esta vacio; falta inicializar el submodulo'; exit 1; }

# Bytecode de los addons propios (mismo motivo que el del fuente; es rapido).
RUN python3 -m compileall -q -j 0 /home/odoo/src/user || true

COPY odoo.conf /home/odoo/.config/odoo/odoo.conf
COPY --chmod=755 entrypoint.sh /entrypoint.sh
# 'odoo-bin' en el PATH, como en Odoo.sh:  docker compose exec odoo odoo-bin shell
RUN ln -s /home/odoo/src/odoo/odoo-bin /usr/local/bin/odoo-bin
# Comandos de operacion (backup...). Se ejecutan DENTRO del contenedor, con su
# misma configuracion:  docker compose exec odoo odoo-backup
COPY --chmod=755 ops/bin/ /usr/local/bin/

LABEL org.opencontainers.image.title="Odoo 19 Enterprise - Importadora Sucre"
LABEL org.opencontainers.image.version="${ODOO_VERSION}"

# Los directorios ya existen y son de 'odoo' (creados arriba): un volumen nuevo
# hereda ese dueño al montarse por primera vez.
VOLUME ["/home/odoo/data", "/home/odoo/backups"]
EXPOSE 8069 8072
WORKDIR /home/odoo
USER odoo
ENTRYPOINT ["/entrypoint.sh"]
