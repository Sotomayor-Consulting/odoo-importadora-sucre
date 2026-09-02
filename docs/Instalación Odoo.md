## Documentación

### Descarga de módulos enterprise (no oficial)

Comandos para descargar

`
tar xzf odoo_19.0+e.latest.tar.gz
cd odoo-19.0*/

# ¿Hay directorio separado de enterprise o está todo mezclado?
ls -d */

# El módulo marcador: si existe web_enterprise, ahí están
find . -maxdepth 3 -name "web_enterprise" -type d

# Cuántos módulos son Enterprise vs Community
grep -rl "OEEL-1" --include=__manifest__.py . | wc -l
grep -rl "LGPL-3" --include=__manifest__.py . | wc -l
`