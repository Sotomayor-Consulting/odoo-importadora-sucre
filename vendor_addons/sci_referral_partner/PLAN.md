# Plan: Módulo `sci_referral_partner` (Odoo 19 Enterprise)

## Contexto

Implementa el **Acuerdo de Colaboración y Referidos Comerciales** de SCI: un *Partner*
(profesional/firma **externa** — relación civil/comercial, no laboral) refiere clientes a SCI
y gana comisión sobre los **honorarios profesionales de SCI efectivamente cobrados** a esos
clientes.

Módulo **independiente de `custom_commissions`** (ese motor es para empleados → nómina).
Toma **las bases del módulo nativo `partner_commission`** (Enterprise) — `referrer_id` en la
venta, **plan + reglas de comisión** por categoría/producto, y pago al referido como
**proveedor** — pero **reimplementadas en este módulo**, porque `partner_commission` depende
de `purchase` + `sale_subscription_partnership` + `website_crm_partner_assign` (website,
suscripciones, programa de resellers) que **no** queremos. Se omite el dashboard de partners.

### Reglas de negocio (del contrato — fuente de la verdad)

- **Cláusula 6 (trazabilidad):** SCI asigna un **código de partner único, personal e
  intransferible**. El cliente se reconoce como referido por trazabilidad (código, enlace,
  formulario, CRM, correo) y confirmación de SCI. SCI verifica legitimidad y si el cliente
  **ya existía**. La mención informal no genera derecho.
- **Cláusula 9 (comisiones):**
  - **15%** incorporación de estructuras (LLC EE.UU., sociedades, holdings, equivalentes).
  - **5%** contabilidad, declaraciones/cumplimiento, agente residente/renovaciones,
    servicios tecnológicos y complementarios.
  - **Base** = honorarios de SCI **cobrados**, excluyendo tasas/fees gubernamentales,
    bancarios y costos de terceros.
  - **Cierre mensual** (mes calendario, servicios **pagados** en el mes).
  - Pago **hasta el día 15 del mes siguiente**, sin mínimo, contra factura/documento válido.
  - **Clawback:** devoluciones/chargebacks → si no se pagó, se anula; si se pagó, se descuenta
    del siguiente pago.
- **Cláusula 18:** la terminación no afecta comisiones ya devengadas.

## Decisiones de diseño (confirmadas)

1. El partner es un **`res.partner` marcado** (`is_referral_partner`).
2. **Base = cobro efectivo** de honorarios SCI (fracción cobrada × subtotal de líneas
   *comisionables*).
3. **Tasa = plan + reglas estilo `partner_commission`**: un `referral.commission.plan` con
   `referral.commission.rule` por **categoría** (sube por ancestros) + producto opcional,
   `rate` y tope. El partner apunta a un plan; el **plan del programa** trae 15%/5%.
4. **Pago = factura de proveedor automática** por el cierre mensual de cada partner.
5. **Código único de partner** (hex aleatorio único) + **auto-asignación por código**: el
   cliente o la orden de venta usan el **código del partner** para quedar vinculados a él.
6. **Sin** dependencia de website/suscripciones/purchase; sin dashboard.

## Modelos de datos

### `res.partner` (inherit)
**Como Partner (referidor):**
- `is_referral_partner` (Boolean).
- `referral_code` (Char, readonly, copy=False, unique) — autogenerado (hex aleatorio único,
  10 caracteres) al marcar `is_referral_partner` (personal e intransferible).
- `referral_commission_plan_id` (M2o `referral.commission.plan`) — plan de tasas del partner
  (default = plan del programa).
- `referral_agreement_date` (Date) — fecha de firma (informativo).
- `referred_partner_ids` (O2m inverse de `referrer_partner_id`), `referred_partner_count`,
  `referral_commission_total` (smart buttons).

**Como Cliente (referido):**
- `referrer_partner_id` (M2o `res.partner`, domain `is_referral_partner=True`) — el partner
  que lo trajo.
- `referral_validated` (Boolean, default False) — SCI confirma legitimidad; **gatilla** la
  comisión (cubre la exclusión de preexistentes).
- `referral_code_entry` (Char) — el cliente/operador escribe el **código del partner**; un
  `onchange`/constraint lo resuelve (`is_referral_partner` con ese `referral_code`) y setea
  `referrer_partner_id`. Si el código no existe o el partner está inactivo → error.

### `referral.commission.plan` — **base de `partner_commission`**
- `name`, `active`, `company_id`.
- `commission_product_id` (M2o `product.product`) — producto usado en la **factura de
  proveedor** de comisiones.
- `rule_ids` (O2m `referral.commission.rule`).
- `_match_rules(product)` — replica `commission.plan._match_rules`: arma los ancestros de
  `product.categ_id` (`parent_path`), busca reglas del plan con `category_id IN ancestros`
  y (`product_id` = product **o** False), ordenadas por `sequence`; devuelve la primera (la
  más específica/prioritaria). Retorna `rate` y, si `is_capped`, aplica `max_commission`.

### `referral.commission.rule`
- `plan_id` (M2o, cascade), `category_id` (M2o `product.category`, **required**),
  `product_id` (M2o, opcional), `rate` (Float 0–100, constraint), `is_capped` (Boolean),
  `max_commission` (Monetary), `sequence`.
- **Seed (`data/referral_plan_data.xml`):** plan "Programa SCI Referidos" con reglas
  categoría *Incorporación* = 15% y categoría raíz (catch-all) = 5%. Se mapea a las
  categorías reales de productos de SCI.

### `product.template` / `product.category` (inherit)
- `referral_commissionable` (Boolean, default True) — si la línea entra en la base. Los
  *pass-through* (tasas gubernamentales, fees bancarios, terceros) se marcan **False**.

### `referral.commission` — comisión devengada (una por línea de factura cobrada)
- `partner_id` (referidor), `customer_id`, `sale_order_id`, `invoice_id`, `invoice_line_id`,
  `product_id`, `company_id`, `currency_id`, `date` (cobro), `period` (mes).
- `base_amount` (honorarios comisionables × fracción cobrada), `collected_fraction`,
  `rate`, `commission_amount`.
- `state` (`draft`/`confirmed`/`settled`/`paid`/`cancelled`), `settlement_id`,
  `is_clawback` / importe negativo en ajustes.

### `referral.commission.settlement` — cierre mensual por partner
- `partner_id`, `date_from`/`date_to` (mes), `company_id`, `currency_id`.
- `line_ids` (O2m `referral.commission`), `amount_total` (computed).
- `payment_due_date` (computed = día 15 del mes siguiente a `date_to`).
- `vendor_bill_id` (M2o `account.move`, `in_invoice`), `state`
  (`draft`/`confirmed`/`billed`/`paid`).
- Acciones: `action_generate`, `action_create_vendor_bill`, `action_mark_paid`,
  `action_reset_to_draft`.

### `sale.order` (inherit) — base de `partner_commission`
- `referrer_id` (M2o `res.partner`, related editable desde `partner_id.referrer_partner_id`)
  — el partner que se lleva la comisión de esta venta.
- `referral_code_entry` (Char) — onchange que resuelve el `referrer_id` por código (igual
  que en el cliente), para atribuir/confirmar la venta.

## Trazabilidad por código (cláusula 6)

- `referral_code` único por partner (hex aleatorio, 10 caracteres, p. ej. `A3F90C12E7`).
- **Auto-asignación:** tanto en el **cliente** (`res.partner`) como en la **orden de venta**,
  el campo "Código de referido" (`referral_code_entry`) resuelve el partner por su código y
  setea `referrer_partner_id`/`referrer_id`. Validación de existencia y partner activo.
- Captura en **backend** (sin website, por decisión). Un formulario público sería una
  extensión opcional futura.

## Motor de cálculo

`settlement.action_generate(partner, period)`:
1. Clientes referidos **validados** del partner.
2. Sus facturas de cliente *posted* con **cobros conciliados en el periodo**;
   `fracción = cobrado_en_periodo / amount_total`.
3. Por `invoice_line` con `product.referral_commissionable`:
   `rate = partner.referral_commission_plan_id._match_rules(product)`;
   `base = price_subtotal × fracción`; `commission_amount = base × rate` (tope si aplica).
4. Emitir `referral.commission`. (Reutiliza la lógica de "fracción cobrada" de
   `custom_commissions._collect_bank`.)
5. **Clawback (Fase 2):** notas de crédito/reembolsos conciliados → líneas negativas.

`action_create_vendor_bill`: `account.move` (`in_invoice`) al `partner_id`, con
`invoice_date_due = payment_due_date`, líneas con `commission_product_id` del plan,
`amount_total = settlement.amount_total`.

## Generación del código
**Código aleatorio en hex mayúsculas con verificación de unicidad** (estilo
`upper(substr(encode(gen_random_bytes(...),'hex'),1,len))`): `secrets.token_hex` →
recorta a 10 caracteres (mín. 6) → reintenta si ya existe. Más "personal e intransferible"
que un secuencial predecible. Override `create`/`write` en `res.partner`: al activar
`is_referral_partner` sin `referral_code`, generar. Constraint SQL de unicidad como respaldo.

## Vistas
- `res.partner` form: página **"Programa de referidos"** — *partner*: `is_referral_partner`,
  `referral_code`, `referral_commission_plan_id`, smart buttons; *cliente*:
  `referral_code_entry`, `referrer_partner_id`, `referral_validated`.
- `referral.commission.plan` / `.rule`: form con reglas + menú.
- `referral.commission`: list/pivot.
- `referral.commission.settlement`: form con líneas + botones generar/facturar/pagar.
- `sale.order`: `referral_code_entry` + `referrer_id` en la pestaña Otra información.
- `product`: `referral_commissionable`.
- Menú **"Referidos"**: Partners, Planes, Comisiones, Liquidaciones.

## Seguridad
`ir.model.access.csv` para modelos nuevos; reglas multi-compañía; configuración (planes,
validación) restringida a un grupo "Gestor de referidos".

## Dependencias
`['sale_management', 'account']`. **No** depende de `purchase`, `sale_subscription_partnership`,
`website_crm_partner_assign` ni timesheet.

## Bases tomadas de `partner_commission` (reimplementadas)
- `referrer_id` en `sale.order`/`account.move`.
- `commission.plan` + `commission.rule` + `_match_rules` (categoría con ancestros, producto
  opcional, `rate`, `is_capped`/`max_commission`).
- Pago al referido como **proveedor** → aquí, `settlement` mensual → **vendor bill**
  (en vez del `purchase.order` por factura del nativo).
- **No** se reutilizan grados (`grade_id`), suscripciones ni website.

## Plan por fases

Cada fase es **instalable/actualizable y testeable de forma independiente** (se valida con
`-u sci_referral_partner --test-enable` antes de pasar a la siguiente). Las fases 0–5 forman
el **MVP**; la 6 es posterior.

### Fase 0 — Andamiaje e instalación
- **Entregables:** `__manifest__.py` (`depends=['sale_management','account']`), `__init__.py`,
  `models/__init__.py`, `security/ir.model.access.csv` (vacío inicial), menú raíz "Referidos".
- **Depende de:** —
- **Criterio:** instala limpio (`-i`); aparece el menú raíz; sin errores de carga.

### Fase 1 — Partner + código único
- **Entregables:** en `res.partner`: `is_referral_partner`, `referral_code` (readonly, único),
  `referral_agreement_date`. Generación **hex aleatorio único** (`secrets`). Override
  `create`/`write` para asignar el código al marcar partner. Constraint de unicidad. Sección
  "Programa de referidos" en el form de contacto.
- **Depende de:** Fase 0.
- **Criterio (test):** marcar `is_referral_partner` genera un `referral_code` único; no se
  regenera al volver a guardar; dos partners no comparten código.

### Fase 2 — Referido + auto-asignación por código
- **Entregables:** en `res.partner` (cliente): `referrer_partner_id`
  (domain `is_referral_partner=True`), `referral_validated`, `referred_partner_ids`/`_count`,
  `referral_code_entry` (onchange que resuelve el partner por su código). En `sale.order`:
  `referrer_id` (related editable desde el cliente) y `referral_code_entry`. Vistas: cliente
  y pestaña "Otra información" de la venta. Smart button "Referidos" en el partner.
- **Depende de:** Fase 1.
- **Criterio (test):** escribir el código del partner en cliente/orden setea
  `referrer_partner_id`/`referrer_id`; código inexistente o partner inactivo → error; la
  cartera (`referred_partner_ids`) lista los clientes vinculados.

### Fase 3 — Plan y reglas de tasa (bases de `partner_commission`)
- **Entregables:** `referral.commission.plan` (con `commission_product_id` y `_match_rules`),
  `referral.commission.rule` (`category_id` required, `product_id` opcional, `rate`,
  `is_capped`/`max_commission`, `sequence`). En `product.template`/`product.category`:
  `referral_commissionable`. En `res.partner`: `referral_commission_plan_id`. Seed
  `data/referral_plan_data.xml` (plan "Programa SCI": 15% incorporación, 5% catch-all).
  Vistas de plan/regla y flag en producto.
- **Depende de:** Fase 0 (independiente de 1–2 a nivel de modelo, pero se entrega después).
- **Criterio (test):** `_match_rules(producto_incorporación)` = 15%; `_match_rules(otro)` =
  5%; una regla con `product_id` específico prevalece sobre la de categoría; el tope aplica.

### Fase 4 — Devengo de comisiones (motor de cobro)
- **Entregables:** `referral.commission` + el colector: por periodo, recorre clientes
  referidos **validados** → sus facturas *posted* con **cobro conciliado en el periodo** →
  `fracción cobrada × subtotal de líneas comisionables × rate` (tope si aplica) → emite
  líneas. Reutiliza la lógica de "fracción cobrada" de `custom_commissions._collect_bank`.
- **Depende de:** Fases 2 y 3.
- **Criterio (test):** factura a cliente referido (15% + 5% + 1 línea pass-through), cobrada
  en el mes → líneas de comisión con base/tasa/importe correctos; la línea pass-through
  queda **excluida**; un cobro parcial escala la base por la fracción.

### Fase 5 — Liquidación mensual → factura de proveedor
- **Entregables:** `referral.commission.settlement` (`date_from`/`date_to`,
  `payment_due_date` = día 15 del mes siguiente, `line_ids`, `amount_total`, `state`),
  `action_generate` (agrupa el devengo del periodo por partner), `action_create_vendor_bill`
  (`in_invoice` al partner, `invoice_date_due`, `commission_product_id`), `action_mark_paid`.
  Vistas + menú de liquidaciones.
- **Depende de:** Fase 4.
- **Criterio (test):** generar la liquidación del mes → líneas correctas y `payment_due_date`
  = día 15; crear la factura de proveedor → `amount_total` = total de comisiones; transición
  de estados `draft→confirmed→billed→paid`.

### Fase 6 — Clawback y reporte (posterior al MVP)
- **Entregables:** notas de crédito/reembolsos conciliados → líneas negativas (`is_clawback`)
  que netean la siguiente liquidación (o anulan si no se pagó). Reporte/exportación mensual.
  Opcional: formulario público de captura de código (introduce dependencia de website, fuera
  del MVP).
- **Depende de:** Fase 5.
- **Criterio (test):** nota de crédito reconciliada contra factura de cliente referido →
  línea negativa que reduce el siguiente settlement.

### Resumen de dependencias entre fases
```
F0 ─┬─ F1 ── F2 ─┐
    └─ F3 ───────┴─ F4 ── F5 ── F6
```

## Verificación
1. Marcar contacto como partner → se genera `referral_code`.
2. En un cliente, escribir el código del partner → se setea `referrer_partner_id`; marcar
   `referral_validated`.
3. Vender (incorporación 15% + servicio 5% + línea pass-through no comisionable), facturar y
   **cobrar** en el mes.
4. Generar liquidación del mes → base solo comisionable × fracción cobrada, tasas vía
   `_match_rules` (15%/5%), `payment_due_date` = día 15 del mes siguiente.
5. Crear factura de proveedor → importe = total de comisiones del periodo.
6. (Fase 2) Nota de crédito reconciliada → línea de clawback negativa.

## Archivos
```
sci_referral_partner/
  __init__.py · __manifest__.py · PLAN.md
  models/__init__.py
    res_partner.py · product_template.py · product_category.py
    referral_commission_plan.py · referral_commission_rule.py
    referral_commission.py · referral_commission_settlement.py · sale_order.py
  data/  referral_plan_data.xml
  security/  referral_security.xml · ir.model.access.csv
  views/  res_partner_views.xml · referral_commission_plan_views.xml
          referral_commission_views.xml · referral_commission_settlement_views.xml
          sale_order_views.xml · product_views.xml · referral_menus.xml
  tests/  __init__.py · test_referral_commission.py
```
