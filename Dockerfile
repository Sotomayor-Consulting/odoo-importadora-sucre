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
    ODOO_RC=/etc/odoo/odoo.conf \
    PYTHONPATH=/opt/odoo \
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

RUN groupadd -g 101 odoo \
 && useradd -u 100 -g 101 -md /var/lib/odoo -s /bin/bash odoo \
 && mkdir -p /etc/odoo /mnt/custom_addons /mnt/vendor_addons /opt/odoo \
 && chown -R odoo:odoo /var/lib/odoo /etc/odoo /mnt/custom_addons /mnt/vendor_addons /opt/odoo

# La URL prefirmada llega como secreto: no queda en ninguna capa ni en
# "docker history". Nunca se imprime, apareceria en los logs de build.
# --strip-components=1 descarta el directorio con fecha, dejando /opt/odoo
# como ruta estable entre versiones.
RUN --mount=type=secret,id=r2_url \
    echo "Compilando Odoo ${ODOO_VERSION}" \
 && curl -fsSL "$(cat /run/secrets/r2_url)" -o /tmp/src.tgz \
 && echo "${ODOO_SHA256}  /tmp/src.tgz" | sha256sum -c - \
 && tar -xzf /tmp/src.tgz -C /opt/odoo --strip-components=1 \
 && rm /tmp/src.tgz \
 && chown -R odoo:odoo /opt/odoo

# Red de seguridad: instala lo que los paquetes de Noble no cubran. La mayoria
# ya estara satisfecha, asi que apenas descarga nada.
RUN pip3 install --no-cache-dir -r /opt/odoo/requirements.txt

COPY --chown=odoo:odoo custom_addons /mnt/custom_addons
COPY --chown=odoo:odoo vendor_addons /mnt/vendor_addons
COPY --chown=odoo:odoo odoo.conf     /etc/odoo/odoo.conf
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

LABEL org.opencontainers.image.title="Odoo 19 Enterprise - Importadora Sucre"
LABEL org.opencontainers.image.version="${ODOO_VERSION}"

VOLUME ["/var/lib/odoo"]
EXPOSE 8069 8072
USER odoo
ENTRYPOINT ["/entrypoint.sh"]
