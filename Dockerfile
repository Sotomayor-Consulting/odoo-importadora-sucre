# Imagen de Odoo 19 Enterprise construida desde cero.
# Base: ubuntu:noble (24.04), la distribucion a cuyas versiones esta pinneado
# el requirements.txt de Odoo ("The officially supported versions ... are their
# python3-* equivalent distributed in Ubuntu 24.04 and Debian 12").
FROM ubuntu:noble

ARG ODOO_VERSION=19.0+e.20260902
ARG ODOO_SHA256=41f56d2adda8ef4369745ad8c6964aa88aace210c2d6cd1c2b8529a1745b2e52
ARG WKHTMLTOPDF_URL=https://github.com/wkhtmltopdf/packaging/releases/download/0.12.6.1-3/wkhtmltox_0.12.6.1-3.jammy_amd64.deb
ARG WKHTMLTOPDF_SHA1=967390a759707337b46d1c02452e2bb6b2dc6d59

ENV LANG=en_US.UTF-8 \
    ODOO_RC=/home/odoo/.config/odoo/odoo.conf \
    PYTHONPATH=/home/odoo/src/odoo \
    DEBIAN_FRONTEND=noninteractive \
    PIP_BREAK_SYSTEM_PACKAGES=1

# Dependencias de sistema. Los python3-* de Noble satisfacen los pines exactos
# del requirements.txt, asi que el pip posterior apenas compila nada.
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl gnupg xz-utils locales \
      postgresql-client \
      nodejs npm node-less \
      fonts-noto fonts-noto-cjk fonts-liberation \
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
#
# Regla de permisos: el CODIGO y la CONFIGURACION son de root y de solo lectura
# para el proceso. El usuario 'odoo' solo puede escribir en data/ (sus datos) y
# en .cache/ y .local/ (caches de herramientas, p. ej. fontconfig al generar
# PDF). Asi, un fallo que permita ejecutar codigo dentro de Odoo no puede
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
             /home/odoo/data /home/odoo/.cache /home/odoo/.local \
 && chown root:root /home/odoo && chmod 755 /home/odoo \
 && chown odoo:odoo /home/odoo/data /home/odoo/.cache /home/odoo/.local

# La URL prefirmada llega como secreto: no queda en ninguna capa ni en
# "docker history". Nunca se imprime, apareceria en los logs de build.
# --strip-components=1 descarta el directorio con fecha, dejando una ruta
# estable entre versiones. --no-same-owner: como root, tar conservaria el
# dueño grabado en el archivo; se fuerza root.
RUN --mount=type=secret,id=r2_url \
    echo "Compilando Odoo ${ODOO_VERSION}" \
 && curl -fsSL "$(cat /run/secrets/r2_url)" -o /tmp/src.tgz \
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

LABEL org.opencontainers.image.title="Odoo 19 Enterprise - Importadora Sucre"
LABEL org.opencontainers.image.version="${ODOO_VERSION}"

# El directorio ya existe y es de 'odoo' (creado arriba): un volumen nuevo
# hereda ese dueño al montarse por primera vez.
VOLUME ["/home/odoo/data"]
EXPOSE 8069 8072
WORKDIR /home/odoo
USER odoo
ENTRYPOINT ["/entrypoint.sh"]
