# Plan: Módulo `custom_commissions` (Odoo 19 Enterprise)

## Contexto

Sotomayor Consulting calcula hoy las comisiones mensuales en una hoja de Excel manual
(`COMISIONES ABRIL 2026.xlsx`) que cruza órdenes de venta, facturas, cobros bancarios y
tareas de proyecto. El objetivo es un módulo Odoo que automatice el cálculo mensual por
equipo CRM, deje trazabilidad por transacción, lo integre con la nómina ecuatoriana y
genere reportes Excel.

La **fuente de la verdad por defecto** sigue siendo el cobro real conciliado en banco,
pero el motor es **parametrizable por regla** para soportar también facturación, órdenes,
tareas cerradas y modelos basados en cantidad (no solo importe). El n8n `Flujo
comisiones.txt` se toma como referencia operativa de qué datos cruza el negocio.

### Referencias
- PDF "Estructura de Comisiones 2026" (tasas y reglas).
- `COMISIONES ABRIL 2026.xlsx` (cálculo manual histórico).
- `Flujo comisiones.txt` (n8n que consolida órdenes → líneas → producto → proyecto →
  tareas → factura → banco → Stripe). Su salida define el conjunto de columnas
  que la línea de detalle del módulo debe poder reproducir.

## Decisiones de diseño (revisadas)

1. **El equipo CRM (`crm.team`) define defaults**: tasa por defecto, descuento de
   sueldo base, método de reparto y reglas. **NO** define qué evento dispara la
   comisión — eso ahora vive en la regla.
2. **La regla (`commission.rate.rule`) define todo lo demás**: frecuencia, tipo
   (qué evento la dispara y qué base usa), criterios (producto/categoría),
   tasa/monto fijo.
3. **La hoja (`commission.sheet`)** itera reglas activas del periodo, despacha al
   colector que corresponda al `rule_type` de cada regla y emite líneas de detalle.
4. **La línea de detalle (`commission.detail.line`)** reproduce las columnas del
   n8n: orden + línea, producto, cantidad, precio total, costo, vendedor, fecha
   orden, cliente, factura, proyecto + snapshot de tarea, banco, transacción de
   pago (Stripe), fee Stripe, regla aplicada.
5. **Ajustes manuales** soportan importe o tasa (% sobre el `commission_amount`
   del empleado en la hoja).

## Modelos de datos

### `commission.sheet` — hoja mensual
Campos clave (sin cambios respecto a la versión anterior salvo lo señalado):

- `name` (computed "Comisiones - <Mes Año>"), `date_from`/`date_to`.
- `team_ids` (M2m `crm.team` con `commission_active=True`).
- `company_ids` (M2m `res.company`), `currency_id`.
- `payslip_period_offset` (Integer, default 1) — desfase mes anterior.
- `include_product_roles`, `include_manual_adjustments` (Boolean).
- `state` (`draft`/`calculated`/`approved`/`paid`).
- `line_ids` (O2m `commission.line`), `detail_line_ids` (O2m
  `commission.detail.line`), `manual_adjustment_ids`.
- Totales: `amount_total`, `employee_count`, `line_count`, `detail_line_count`.

Acciones:
- `action_calculate`: limpia y recalcula. Itera **reglas** (no equipos): para cada
  regla activa del periodo, despacha por `rule_type` al colector correspondiente.
- `action_approve` → `approved` (+ `_sync_payslip_inputs` en Fase 6).
- `action_mark_paid`, `action_reset_to_draft`.

Restricción: `date_to >= date_from`, `payslip_period_offset >= 0`.

### `commission.rate.rule` — **eje del motor**

Esta es la unidad de cálculo. Cada regla declara cómo se calcula y qué dispara.

Campos:

| Campo | Tipo | Descripción |
|---|---|---|
| `name` | Char | Etiqueta. |
| `team_id` | M2o `crm.team` | Equipo dueño. |
| `company_id` | M2o `res.company` related | Multi-compañía. |
| `sequence` | Integer | Prioridad dentro del nivel de matching. |
| `active` | Boolean | Permite desactivar promos. |
| `frequency` | Selection | `monthly` (default), `quarterly`, `yearly`. La regla solo aplica si el periodo de la hoja encaja con su frecuencia (ver `_period_matches`). |
| `rule_type` | Selection | **Qué evento dispara la comisión y sobre qué base**: <br>· `bank_paid` — cobro conciliado (default; modo histórico) <br>· `invoice_paid` — factura emitida con cobro en el periodo <br>· `invoice` — factura emitida en el periodo (importe facturado) <br>· `order` — orden confirmada en el periodo (importe vendido) <br>· `margin` — margen = ingreso − costo (de cuenta analítica) sobre el cobrado o lo facturado, según `amount_basis` <br>· `qty_invoiced` — cantidad facturada (Σ `qty_invoiced` × `rate` o `× fixed_amount`) <br>· `qty_sold` — cantidad vendida (Σ `product_uom_qty` de SO) |
| `amount_basis` | Selection | `revenue` (default), `margin`. Solo relevante en `bank_paid`/`invoice_paid`/`invoice`/`order` para conmutar entre importe pre-impuesto y margen. |
| `product_ids` | M2m `product.product` | Criterio más específico. |
| `product_category_ids` | M2m `product.category` | Criterio por categoría (sube por `categ_id.parent_id`). |
| `computation_type` | Selection | `percentage`/`fixed`. |
| `rate` | Float | Tasa %. |
| `fixed_amount` | Monetary | Para reglas tipo "X $ por unidad" combinado con `qty_*`. |
| `notes` | Char | |

Vendedores: campo computado `seller_user_ids = related team_id.member_ids` solo
para visualización; el reparto efectivo se hace en el motor según
`team.commission_split_method`.

Métodos:

- `_period_matches(date_from, date_to)`: True si la frecuencia encaja con el rango
  de la hoja (mensual = siempre; trimestral = solo si el rango cubre un trimestre
  fiscal; anual = solo si cubre el año completo o si el `date_from.month == 1` y
  el rango es todo el año). Configurable; por ahora exige cobertura exacta del
  periodo objetivo, con una nota de TODO para flexibilizar.
- `_match(product, team, company)`: misma precedencia que la versión actual
  (producto → categoría → catch-all), pero ya no se filtra por frecuencia aquí; el
  colector lo hace antes. Se mantiene para que el motor pueda elegir la regla
  más específica entre las del mismo `rule_type` para un producto dado.
- `compute_commission(base_amount, quantity=None)`: aplica la regla. Para
  `qty_*` con `fixed_amount` → `fixed_amount × quantity`.

### `commission.detail.line` — **detalle por transacción (renombrado desde `commission.detail.log`)**

Reproduce las columnas del n8n. Cada registro vincula una transacción origen
(orden+línea, factura, banco, tarea o Stripe) con una `commission.line`.

| Campo | Tipo | Origen / nota |
|---|---|---|
| `line_id` | M2o `commission.line` cascade | Agrupador por empleado/equipo. |
| `sheet_id`, `employee_id`, `team_id`, `user_id`, `company_id`, `currency_id` | related store | Para record rules y pivots. |
| `source` | Selection | `team`/`product_role`/`manual` (igual que antes). |
| `rule_id` | M2o `commission.rate.rule` | Regla aplicada. |
| `rule_type` | related `rule_id.rule_type` store | Para reportes/filtrado. |
| `date` | Date | Fecha del evento que dispara la comisión (cobro, emisión, confirmación, cierre tarea). |
| `order_date` | Date | Fecha de la orden de venta (n8n: `FechaOrden`). |
| `partner_id` | M2o `res.partner` | Cliente. |
| `sale_order_id` | M2o `sale.order` | |
| `sale_order_line_id` | M2o `sale.order.line` | |
| `product_id` | M2o `product.product` | Servicio. |
| `quantity` | Float | `sale.order.line.product_uom_qty` (n8n: `Cantidad`). |
| `price_total` | Monetary | `sale.order.line.price_total` (con impuestos). |
| `cost_amount` | Monetary | `product.standard_price × quantity` (snapshot) o Σ `account.analytic.line` del proyecto si hay cuenta analítica. |
| `invoice_id` | M2o `account.move` | Factura. |
| `bank_statement_line_id` | M2o `account.bank.statement.line` | Cobro. |
| `payment_transaction_id` | M2o `payment.transaction` | Stripe/proveedor. |
| `stripe_fee` | Monetary | Snapshot del fee (`x_studio_fee_stripe` o Stripe API). |
| `project_id` | M2o `project.project` | Proyecto reinvoiced del SO. |
| `analytic_account_id` | M2o `account.analytic.account` | Para margen. |
| `project_last_update_status` | Selection | Snapshot del estado del proyecto (on_track/at_risk/off_track/on_hold/done). |
| `project_task_id` | M2o `project.task` | Tarea del sale line. |
| `task_state` | Char | Snapshot (`stage_id.name` / state label). |
| `task_stage` | Char | Snapshot (`stage_id.name`). |
| `task_user_names` | Char | Snapshot (`user_ids.name` separados por coma). |
| `task_date_last_stage_update` | Datetime | Snapshot. |
| `description` | Char | Texto libre (la línea de orden o el motivo del ajuste). |
| `base_amount` | Monetary | Base sobre la que se aplica la regla (price_subtotal × fracción cobrada, o margen, según `rule_type`). |
| `rate` | Float | Tasa aplicada. |
| `fixed_amount` | Monetary | Monto fijo aplicado (`qty_*` o regla `fixed`). |
| `commission_amount` | Monetary | Comisión final del log. |

> **Snapshot vs. related**: los campos de tarea y proyecto son **snapshot** (no
> related), porque la tarea puede cambiar después de calcular la hoja y queremos
> congelar el estado del momento del cálculo. Sí son `related` los IDs (`sheet_id`,
> `employee_id`, etc.) porque dependen de la línea.

### `commission.line` — agrupador empleado × equipo (sin cambios estructurales)

Campos relevantes:
- `sheet_id`, `team_id`, `employee_id`, `user_id`, `company_id`, `source`.
- `base_revenue`, `base_cost`, `base_margin`, `base_amount` (todos computed
  desde `detail_line_ids`).
- `commission_amount` (Σ logs), `base_salary_deduction`, `net_amount`.
- `detail_line_ids` (O2m a `commission.detail.line`, antes era `detail_log_ids`).
- `detail_count`.

Cambios:
- `detail_log_ids` → `detail_line_ids` (rename del campo y de la One2many target).
- `base_cost` ya no es default 0.0 sino computed: Σ `detail_line_ids.cost_amount`.
- `base_margin = base_revenue − base_cost` (computed).

### `commission.manual.adjustment` — con tasa

Campos:
- `sheet_id`, `employee_id`, `team_id`, `company_id`, `currency_id`.
- `reason` (`trustpilot`/`correction`/`bonus`/`other`).
- `date` (default hoy), `description` (required).
- **`adjustment_mode`** (Selection: `fixed` default, `percentage`).
- `amount` (Monetary) — usado si `adjustment_mode == 'fixed'`.
- `rate` (Float) — usado si `adjustment_mode == 'percentage'`.
- `base_reference` (Selection: `commission`/`net`) — base sobre la cual se aplica
  el %. `commission` = `commission_amount` del empleado en la hoja antes del
  descuento de sueldo; `net` = después del descuento.
- `computed_amount` (Monetary, computed): el importe final que se reflejará en la
  línea, ya sea `amount` (modo fixed) o el % calculado al momento del cálculo.

Restricción: el modo `percentage` requiere `rate > 0`; el modo `fixed` requiere
`amount != 0`.

### `crm.team` — **limpieza**

**Mantener**:
- `commission_active`.
- `commission_computation`, `commission_rate`, `commission_fixed_amount` (default
  catch-all que se aplica cuando ninguna regla matchea).
- `commission_base_salary_deduction` (USD 800).
- `commission_split_method` (`seller`/`equal`/`task_assignee`).
- `commission_rate_rule_ids`, `commission_rate_rule_count`.

**Eliminar** (suben a la regla):
- `commission_basis`.
- `commission_amount_basis`.

### `hr.employee` — sin cambios
`commission_base_salary` (override del default del equipo).

## Motor (`commission.sheet._collect_*`)

### Dispatcher

```python
def _collect_sales_details(self):
    rules = self._collect_applicable_rules()  # filtradas por frecuencia, periodo, equipo activo
    # Agrupar por rule_type para evitar trabajo duplicado (un solo scan de banco, etc.)
    by_type = defaultdict(lambda: self.env['commission.rate.rule'])
    for r in rules: by_type[r.rule_type] |= r
    if by_type['bank_paid']: self._collect_bank(by_type['bank_paid'])
    if by_type['invoice_paid'] or by_type['invoice']:
        self._collect_invoice(by_type['invoice_paid'] | by_type['invoice'])
    if by_type['order']:        self._collect_order(by_type['order'])
    if by_type['qty_invoiced']: self._collect_qty(by_type['qty_invoiced'])
    if by_type['qty_sold']:     self._collect_qty(by_type['qty_sold'])
    if by_type['margin']:       self._collect_margin(by_type['margin'])
    # task_done queda como sub-modo del colector de operaciones (Fase 4+).
```

### Colectores

1. **`_collect_bank(rules)`** (default histórico)
   - Scan `bank.statement.line` en periodo con `amount > 0`.
   - Cruzar `matching_number` con `account.move.line` receivable de facturas
     posted del periodo.
   - Para cada factura: `fracción = cobrado / amount_total`.
   - Para cada `invoice.invoice_line_ids` con `sale_line_ids` cuyo `team_id`
     coincida con el `team_id` de alguna regla del set:
     - Tomar la regla más específica que matchee (`_match(product, team, company)`)
       dentro de las reglas pasadas.
     - `base = price_subtotal × fracción`.
     - Empleado = `_split_employee_amounts(team, sale_line, base)`.
     - Emitir `commission.detail.line` con todos los campos snapshot (incluye
       `payment_transaction_id` resuelto vía `account.payment.payment_transaction_id`
       si la factura se pagó por Stripe).

2. **`_collect_invoice(rules)`** — fusiona `invoice` (importe facturado) y
   `invoice_paid` (factura cuyo pago cayó en el periodo).
   - `invoice_paid`: misma lógica que `bank`, pero la base es 100% del subtotal
     de la línea (no escalada por fracción cobrada) si la factura tiene **cualquier**
     pago en el periodo.
   - `invoice`: facturas posted con `invoice_date` en periodo. Base = `price_subtotal`
     de la línea. No requiere conciliación.

3. **`_collect_order(rules)`** — órdenes confirmadas en el periodo (n8n base).
   - `sale.order` con `state = 'sale'`, `date_order` en periodo, compañías en
     alcance, team_id en reglas.
   - Base = `price_subtotal` de la línea.
   - Recorre `order.order_line.filtered(lambda l: l.display_type == 'product' and l.product_id.id not in EXCLUDED_PRODUCT_REFS)`.

4. **`_collect_qty(rules)`** — comisiones por unidad.
   - `qty_invoiced`: Σ `sale_line.qty_invoiced` de líneas de SO cuyas facturas
     posted están en periodo.
   - `qty_sold`: Σ `sale_line.product_uom_qty` de SO confirmadas en periodo.
   - Comisión = `quantity × fixed_amount` (si la regla es `fixed`) o
     `quantity × price_subtotal_unit × rate%` (si la regla es `percentage`,
     no muy usado pero soportado).

5. **`_collect_margin(rules)`** — combina `amount_basis = margin` con cualquier
   evento disparador.
   - Para cada origen (cobrado/facturado/vendido según `amount_basis` lookup), la
     base es `base_revenue − base_cost`. `base_cost` se calcula desde
     `account.analytic.line` del `analytic_account_id` del proyecto del SO o del
     `product.standard_price × quantity` si no hay analítica.

6. **`task_done`** — Operaciones (sin cambios respecto al PLAN anterior; usa
   `project.task.commission_done_date`). Se mantiene como sub-modo cubierto por
   un colector dedicado en Fase 4.

### Helpers compartidos

- `_resolve_payment_transaction(invoice)`: recorre `invoice.matched_payment_ids
  .payment_transaction_id` (`account.payment` enlaza a Stripe). Fallback a buscar
  `payment.transaction` con `sale_order_ids` que contenga el SO.
- `_snapshot_task(sale_line)`: `task = sale_line.task_id` o `sale_line.task_ids[:1]`.
  Devuelve dict con `task_state`, `task_stage`, `task_user_names`, etc.
- `_snapshot_project(sale_line)`: `project_id = sale_line.task_id.project_id` o el
  proyecto que tenga `reinvoiced_sale_order_id == sale_line.order_id`.

## Integración con nómina (Fase 6, sin cambios)

`hr.payslip.input.type` `COMMISSION_TOTAL`, `hr.salary.rule` en
`l10n_ec_payroll_structure_employee` con `amount_python_compute` leyendo el helper
existente. `_sync_payslip_inputs` y override en `hr.payslip` para tolerar el orden
aprobar↔generar nómina.

## Reportes (Fase 7, sin cambios mayores)

El wizard genera Excel **General** (1 fila por empleado/equipo) y **Por empleado**
(1 fila por `commission.detail.line` con todas las columnas del n8n).

## Vistas

- `commission.rate.rule`: añadir `frequency`, `rule_type`, `amount_basis`. El
  campo `rate`/`fixed_amount` cambia visibilidad según `computation_type` y
  `rule_type`.
- `commission.detail.line`: list/form/pivot. La list muestra columnas tipo n8n:
  `date`, `order_date`, `partner_id`, `sale_order_id`, `product_id`, `quantity`,
  `price_total`, `cost_amount`, `invoice_id`, `bank_statement_line_id`,
  `payment_transaction_id`, `project_id`, `task_state`, `base_amount`, `rate`,
  `commission_amount`.
- `commission.sheet`: la pestaña "Logs de detalle" pasa a "Líneas de detalle"
  con el nuevo modelo y columnas.
- `crm.team`: quitar `commission_basis` y `commission_amount_basis` del form.
- `commission.manual.adjustment`: añadir `adjustment_mode`, `rate`,
  `base_reference`, `computed_amount`. Toggles de visibilidad en el form/list.

## Seguridad

`ir.model.access.csv`: renombrar entradas de `commission.detail.log` a
`commission.detail.line`. Reglas en `commission_security.xml` referencian
`model_commission_detail_line` (Odoo genera el `model_*` ID automáticamente).

## Datos semilla

Tras la migración del modelo, los XML de `data/` siguen apuntando a tasas por
defecto del equipo y reglas catch-all del PDF (5% ventas, 20% operaciones).
Pendiente: poblar `data/commission_rate_rule_data.xml` con reglas tipadas
(`rule_type='bank_paid'`, `amount_basis='revenue'`) para los 4 grupos del PDF.

## Archivos

```
custom_commissions/
  __init__.py · __manifest__.py · PLAN.md
  models/__init__.py
    commission_sheet.py · commission_line.py · commission_detail_line.py
    commission_rate_rule.py · commission_manual_adjustment.py
    crm_team.py · hr_employee.py
  security/  commission_security.xml · ir.model.access.csv
  views/  commission_sheet_views.xml · commission_line_views.xml
          commission_detail_line_views.xml · commission_rate_rule_views.xml
          crm_team_views.xml · hr_employee_views.xml · commission_menus.xml
  data/  (pendiente: commission_rate_rule_data.xml)
  wizards/  (Fase 7: commission_report_wizard.py)
```

## Migración

El módulo está en desarrollo activo y aún no se ha cargado data productiva, por lo
que la migración del modelo `commission.detail.log` → `commission.detail.line` se
hace con un `-u custom_commissions` tras renombrar (Odoo borra el modelo viejo
y crea el nuevo). Si en algún punto hubiera data, hay que añadir un script
`migrations/19.0.1.1.0/post-rename.py`.

## Verificación

1. Reinstalar con `-u custom_commissions` en WSL.
2. Crear hoja "Comisiones - Abril 2026" con `team_ids = [Ventas]`, `date_from = 2026-04-01`,
   `date_to = 2026-04-30`.
3. Configurar al menos una regla por equipo:
   - "Ventas catch-all 5% cobrado" — `rule_type=bank_paid`, `amount_basis=revenue`,
     `frequency=monthly`, `computation=percentage`, `rate=5`.
   - "Ventas LLC 10% cobrado" — igual pero con `product_category_ids` apuntando a
     "Venta de LLCs".
4. **Calcular**. Verificar:
   - `commission.detail.line` con todas las columnas del n8n.
   - `payment_transaction_id` resuelto en facturas pagadas con Stripe.
   - `cost_amount` poblado (al menos desde `standard_price` si no hay analítica).
   - `task_state`/`task_stage`/`task_user_names` snapshot.
5. Cambiar la regla a `rule_type=order` y recalcular: debe tomar como base las SOs
   confirmadas en el periodo (no las facturas).
6. Añadir un ajuste manual en modo porcentaje (`adjustment_mode=percentage`,
   `rate=10`, `base_reference=commission`): el `computed_amount` debe ser el 10%
   del `commission_amount` del empleado.

## Supuestos y pendientes

- `_period_matches` empieza estricto (trimestral exige cubrir trimestre fiscal,
  anual exige cubrir año completo). Si se necesita más flexibilidad (ej. "regla
  anual prorrateada"), se itera después.
- `qty_*` y `margin` quedan implementados pero **sin reglas semilla**; el usuario
  los activa creando una regla manualmente.
- Stripe fee se captura informativo. No se descuenta del ejecutivo (eso seguiría
  alimentando un pool de gerencia, fuera de alcance).
- Si una factura tiene varias `payment.transaction`, se toma la última `done` con
  `provider_code='stripe'`.
