# Sotomayor Consulting — Addons Odoo 19 Enterprise

Colección de módulos personalizados de **Odoo 19 Enterprise** para Sotomayor Consulting
(incorporación de empresas y servicios contables EE.UU./Ecuador). Este repositorio contiene
únicamente los addons custom; el core de Odoo se ejecuta por separado.

> Para guía de desarrollo, arquitectura y entorno ver [CLAUDE.md](CLAUDE.md).

## Módulos

| Módulo | Propósito |
| --- | --- |
| `l10n_ec_hr_payroll` | Base de nómina Ecuador (IESS, décimo 13/14, fondos de reserva, quincena) sobre `hr.version`. |
| `l10n_ec_hr_payroll_account` | Capa contable de la nómina ecuatoriana. |
| `sci_companies_management` | Gestión integral de entidades legales (LLCs): miembros, agente residente, documentos, FinCEN. |
| `wire_transfer_payment_flow` | Flujo de pago multi-compañía; crea proyecto/tareas según estado de pago y conciliación bancaria. |
| `payment_stripe_fee` | Manejo del fee de Stripe en proveedores de pago. |
| `payment_bank_transfer_receipt` | Subida de comprobante para pagos por transferencia. |
| `custom_commissions` | *(En construcción)* Comisiones mensuales de Ventas y Operaciones con integración a nómina y reportes Excel. Ver [PLAN.md](custom_commissions/PLAN.md). |

## Entorno

- **Odoo 19 Enterprise** instalado como paquete Debian dentro de **WSL Ubuntu-24.04**
  (binario `/usr/bin/odoo`, config `/etc/odoo/odoo.conf`, servicio systemd `odoo`).
- PostgreSQL 18.
- El repositorio se monta en WSL como `/mnt/c/Proyectos/sotomayorconsulting` y está en el
  `addons_path`. Se edita desde Windows y se ejecuta desde WSL.

## Instalar / actualizar un módulo

```bash
wsl -d Ubuntu-24.04
sudo systemctl stop odoo
sudo -u odoo odoo -c /etc/odoo/odoo.conf -d <BD> -u <modulo> --stop-after-init
sudo systemctl start odoo
```

También desde la UI: **Apps → Actualizar lista de aplicaciones → Instalar / Actualizar**.

## Licencia

LGPL-3.
