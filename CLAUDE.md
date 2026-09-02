# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Qué es este repositorio

Colección de **addons personalizados de Odoo 19 Enterprise** para Sotomayor Consulting
(incorporación de empresas y servicios contables EE.UU./Ecuador). El repositorio contiene
**solo los módulos custom**; el core de Odoo/Enterprise se ejecuta por separado. La empresa
opera con dos compañías (Sotomayor Consulting Ecuador y Sotomayor Consulting International),
ambas en USD.

## Entorno y comandos — Odoo corre en WSL, NO en Windows

Odoo 19 Enterprise (`19.0+e`) está instalado como paquete Debian dentro de **WSL Ubuntu-24.04**:
- Binario `/usr/bin/odoo` · Config `/etc/odoo/odoo.conf` (requiere sudo) · Log
  `/var/log/odoo/odoo-server.log` · Servicio systemd `odoo` · PostgreSQL 18 (servicio Windows).
- El repo (Windows `C:\Proyectos\sotomayorconsulting`) se ve en WSL como
  `/mnt/c/Proyectos/sotomayorconsulting` y ya está en el `addons_path`. **Edita archivos desde
  Windows; ejecuta Odoo desde WSL** (el mount es compartido y en vivo).

Ejecutar cualquier comando de Odoo: `wsl -d Ubuntu-24.04 -- bash -lc '<cmd>'`
- Instalar/actualizar un módulo:
  `sudo systemctl stop odoo` → `sudo -u odoo odoo -c /etc/odoo/odoo.conf -d <BD> -u <modulo> --stop-after-init` → `sudo systemctl start odoo`
  (o vía la UI: Apps → Actualizar lista → Instalar/Actualizar). El nombre de `<BD>` está en el conf; pídelo al usuario.
- Correr tests de un módulo:
  `sudo -u odoo odoo -c /etc/odoo/odoo.conf -d <BD> -u <modulo> --test-enable --stop-after-init`
- Correr un solo test:
  `... --test-enable --test-tags /<modulo>:<ClaseTest>.<metodo> --stop-after-init`
  (Aún no hay suites de test propias en el repo.)
- Generar un módulo nuevo: `odoo scaffold <nombre> /mnt/c/Proyectos/sotomayorconsulting`
- Ver logs: `tail -f /var/log/odoo/odoo-server.log`
- Inspeccionar el fuente Enterprise instalado: `/usr/lib/python3/dist-packages/odoo/addons/...`
- Quoting Windows→WSL: evita comillas dobles internas y `|` dentro de alternancias de `grep`
  (rompen el paso de argumentos); prefiere `pgrep -af`.

## Arquitectura (panorama)

Los addons modelan en conjunto este flujo de negocio:
**orden de venta → factura → pago y conciliación bancaria → proyecto/tareas (entrega) →
comisiones → nómina.** Dos dominios:

### Localización de nómina Ecuador
- `l10n_ec_hr_payroll`: base de nómina EC sobre Odoo 19 Enterprise. En Odoo 19 el contrato es
  **`hr.version`** (no `hr.contract`). Define la estructura `l10n_ec_payroll_structure_employee`,
  categorías `l10n_ec_salary_rule_category_*` y reglas salariales (IESS, décimo 13/14, fondos de
  reserva, quincena, NET). Las reglas usan `amount_python_compute` y leen entradas de nómina vía
  el helper **`payslip._l10n_ec_get_input_amount(code)`**; la config por empleado vive como campos
  en `hr.version`.
- `l10n_ec_hr_payroll_account`: capa contable de la nómina (depende de `hr_payroll_account`).

### Ventas / pagos / operaciones
- `sci_companies_management`: gestión integral de entidades legales (`sci_companies_management.entity` + modelos
  `entity.*`: miembros, agente residente, documentos, reporte FinCEN). App con portal público
  (controlador) y assets JS.
- `wire_transfer_payment_flow`: condiciona la creación de proyecto/tareas según el estado de pago
  (`wpf_project_creation_policy`: `on_confirm`/`on_first_payment`/`on_paid`). Las líneas de venta
  de servicios generan `project.task` vía `sale_project`. La **conciliación bancaria** es el
  disparador de "pagado".
- `payment_stripe_fee`, `payment_bank_transfer_receipt`: extensiones de proveedores de pago
  (fee de Stripe; subida de comprobante de transferencia).
- `custom_commissions` *(en construcción — ver `custom_commissions/PLAN.md`)*: comisiones
  mensuales para **Ventas** (% sobre el valor de venta efectivamente cobrado; fuente de la verdad =
  `account.bank.statement.line` conciliada; menos USD 800 de anticipo) y **Operaciones** (20% del
  honorario de cada `project.task` cerrada en el mes), que alimentan la nómina mediante una entrada
  `COMMISSION_TOTAL`. **El diseño, las reglas de negocio y el backlog están en
  `custom_commissions/PLAN.md` — léelo antes de implementar.**

## Convenciones de módulo

- Manifest: `author` 'Sotomayor Consulting International', `website`, `license` 'LGPL-3',
  `version` '19.0.1.0.0' (módulos nuevos), `depends` explícito.
- Modelos con `_name` en notación de puntos; chatter vía `mail.thread` (+ `mail.activity.mixin`);
  textos de UI en español; comentarios mínimos (sin redundancias). Algunos strings computados
  evitan acentos.
- Contrato de integración con nómina: agrega un `hr.payslip.input.type` con `code` único + una
  `hr.salary.rule` sobre `l10n_ec_payroll_structure_employee` que lo lea con
  `_l10n_ec_get_input_amount('<CODE>')`.

## Notas

- No ejecutes Odoo desde PowerShell — vive en WSL.
- `__pycache__`/`*.pyc` no deben commitearse (el `.gitignore` debe excluirlos).
