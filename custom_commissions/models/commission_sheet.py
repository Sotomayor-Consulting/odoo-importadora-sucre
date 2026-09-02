import logging
from collections import defaultdict
from datetime import date, timedelta

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError

_logger = logging.getLogger(__name__)

MONTHS_ES = [
    'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
    'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre',
]

TASK_STATE_LABELS = {
    '01_in_progress': 'En progreso',
    '02_changes_requested': 'Cambios solicitados',
    '03_approved': 'Aprobada',
    '04_waiting_normal': 'Esperando',
    '1_done': 'Hecha',
    '1_canceled': 'Cancelada',
}


class CommissionSheet(models.Model):
    _name = 'commission.sheet'
    _description = 'Hoja mensual de comisiones'
    _order = 'date_from desc, id desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(
        compute='_compute_name',
        store=True,
        precompute=True,
        readonly=False,
        required=True,
        tracking=True,
    )

    date_from = fields.Date(
        string='Desde',
        required=True,
        default=lambda self: date.today().replace(day=1),
        tracking=True,
    )
    date_to = fields.Date(
        string='Hasta',
        required=True,
        default=lambda self: self._default_date_to(),
        tracking=True,
    )

    team_ids = fields.Many2many(
        'crm.team',
        string='Equipos',
        default=lambda self: self.env['crm.team'].search([('commission_active', '=', True)]),
        help='Equipos CRM cuyo calculo se consolida en la hoja.',
    )

    company_ids = fields.Many2many(
        'res.company',
        string='Companias',
        required=True,
        default=lambda self: self.env.companies,
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Moneda',
        default=lambda self: self.env.company.currency_id,
        required=True,
    )

    # ------------------------------------------------------------------
    # Parametro principal: fuente de datos.
    # Define que se obtiene en action_collect_data.
    # ------------------------------------------------------------------
    data_source = fields.Selection(
        [
            ('bank_paid', 'Pago conciliado (transacciones bancarias)'),
            ('invoice_paid', 'Factura con pago en el periodo'),
            ('invoice', 'Importe facturado'),
            ('order', 'Orden confirmada'),
        ],
        string='Fuente de datos',
        default='bank_paid',
        required=True,
        tracking=True,
        help=(
            'Que evento dispara la obtencion de datos:\n'
            '- Pago conciliado: bank.statement.line conciliada con facturas en periodo.\n'
            '- Factura pagada: factura con pago efectivo en el periodo (base completa).\n'
            '- Importe facturado: facturas emitidas en periodo (sin requerir cobro).\n'
            '- Orden confirmada: sale.order state=sale con date_order en periodo.'
        ),
    )

    include_product_roles = fields.Boolean(
        string='Incluir roles por producto',
        default=True,
    )
    include_manual_adjustments = fields.Boolean(
        string='Incluir ajustes manuales',
        default=True,
    )

    payslip_period_offset = fields.Integer(
        string='Desfase de nomina (meses)',
        default=1,
        help=(
            'Numero de meses a sumar al periodo de la hoja para encontrar la nomina '
            'donde se debe inyectar la comision. Por defecto 1: comisiones de abril '
            'se pagan en la quincena de mayo.'
        ),
    )

    state = fields.Selection(
        [
            ('draft', 'Borrador'),
            ('collected', 'Datos obtenidos'),
            ('calculated', 'Calculada'),
            ('approved', 'Aprobada'),
            ('paid', 'Pagada'),
        ],
        default='draft',
        required=True,
        tracking=True,
    )

    line_ids = fields.One2many(
        'commission.line',
        'sheet_id',
        string='Lineas',
    )
    detail_line_ids = fields.One2many(
        'commission.detail.line',
        'sheet_id',
        string='Lineas de detalle',
    )
    manual_adjustment_ids = fields.One2many(
        'commission.manual.adjustment',
        'sheet_id',
        string='Ajustes manuales',
    )

    amount_total = fields.Monetary(
        compute='_compute_totals',
        store=True,
        currency_field='currency_id',
        tracking=True,
    )
    employee_count = fields.Integer(compute='_compute_totals', store=True)
    line_count = fields.Integer(compute='_compute_totals', store=True)
    detail_line_count = fields.Integer(compute='_compute_detail_line_count')

    notes = fields.Html(string='Notas')

    # ---------------------------------------------------------------------
    # Defaults
    # ---------------------------------------------------------------------
    @api.model
    def _default_date_to(self):
        today = date.today()
        if today.month == 12:
            return today.replace(day=31)
        first_next = today.replace(day=1, month=today.month + 1)
        return first_next - timedelta(days=1)

    # ---------------------------------------------------------------------
    # Computed
    # ---------------------------------------------------------------------
    @api.depends('date_from', 'date_to')
    def _compute_name(self):
        for sheet in self:
            if not sheet.date_from or not sheet.date_to:
                sheet.name = _('Comisiones (sin periodo)')
                continue
            same_month = (
                sheet.date_from.year == sheet.date_to.year
                and sheet.date_from.month == sheet.date_to.month
            )
            if same_month:
                month = MONTHS_ES[sheet.date_from.month - 1]
                sheet.name = f'Comisiones - {month} {sheet.date_from.year}'
            else:
                sheet.name = f'Comisiones - {sheet.date_from} a {sheet.date_to}'

    @api.depends('line_ids.net_amount', 'line_ids.employee_id')
    def _compute_totals(self):
        for sheet in self:
            sheet.amount_total = sum(sheet.line_ids.mapped('net_amount'))
            sheet.line_count = len(sheet.line_ids)
            sheet.employee_count = len(sheet.line_ids.mapped('employee_id'))

    def _compute_detail_line_count(self):
        for sheet in self:
            sheet.detail_line_count = len(sheet.detail_line_ids)

    # ---------------------------------------------------------------------
    # Constraints
    # ---------------------------------------------------------------------
    @api.constrains('date_from', 'date_to')
    def _check_period(self):
        for sheet in self:
            if sheet.date_from and sheet.date_to and sheet.date_to < sheet.date_from:
                raise ValidationError(_('La fecha "Hasta" debe ser posterior o igual a "Desde".'))

    @api.constrains('payslip_period_offset')
    def _check_offset(self):
        for sheet in self:
            if sheet.payslip_period_offset < 0:
                raise ValidationError(_('El desfase de nomina no puede ser negativo.'))

    # =====================================================================
    # State machine + acciones
    # =====================================================================
    def action_collect_data(self):
        """Obtiene los datos segun data_source, SIN aplicar reglas."""
        for sheet in self:
            if sheet.state not in ('draft', 'collected', 'calculated'):
                raise UserError(_(
                    'Solo se pueden obtener datos en estado borrador, obtenido o calculado.'
                ))
            sheet._reset_computed_data()
            sheet._collect_manual_adjustments()
            sheet._collect_data()
            sheet.invalidate_recordset()
            sheet.state = 'collected'
            sheet.message_post(body=_(
                'Datos obtenidos. Lineas de detalle: %s'
            ) % sheet.detail_line_count)
        return True

    def action_calculate(self):
        """Aplica reglas a las detail lines ya obtenidas."""
        for sheet in self:
            if sheet.state == 'draft':
                # Si nunca se obtuvieron datos, hacer ambos pasos.
                sheet.action_collect_data()
            if sheet.state not in ('collected', 'calculated'):
                raise UserError(_(
                    'Solo se puede calcular tras obtener datos.'
                ))
            sheet._apply_rules()
            sheet.invalidate_recordset()
            sheet.state = 'calculated'
            sheet.message_post(body=_(
                'Hoja calculada. Lineas: %s, Total: %s'
            ) % (sheet.line_count, sheet.amount_total))
        return True

    def action_approve(self):
        for sheet in self:
            if sheet.state != 'calculated':
                raise UserError(_('Solo se pueden aprobar hojas en estado calculada.'))
            sheet.state = 'approved'
            sheet.message_post(body=_('Hoja aprobada.'))
        return True

    def action_mark_paid(self):
        for sheet in self:
            if sheet.state != 'approved':
                raise UserError(_('Solo se pueden marcar pagadas hojas aprobadas.'))
            sheet.state = 'paid'
            sheet.message_post(body=_('Hoja marcada como pagada.'))
        return True

    def action_reset_to_draft(self):
        for sheet in self:
            if sheet.state == 'paid':
                raise UserError(_('No se puede devolver a borrador una hoja pagada.'))
            sheet._reset_computed_data()
            sheet.state = 'draft'
            sheet.message_post(body=_('Hoja devuelta a borrador.'))
        return True

    # =====================================================================
    # Helpers de reset / ajustes manuales
    # =====================================================================
    def _reset_computed_data(self):
        self.ensure_one()
        self.line_ids.unlink()
        return True

    def _collect_manual_adjustments(self):
        """Convierte ajustes manuales en lineas + detail lines."""
        self.ensure_one()
        if not self.include_manual_adjustments:
            return
        Line = self.env['commission.line']
        DetailLine = self.env['commission.detail.line']
        groups = {}
        for adj in self.manual_adjustment_ids:
            key = (adj.employee_id.id, adj.team_id.id or False, adj.company_id.id)
            groups.setdefault(key, []).append(adj)
        for (employee_id, team_id, company_id), adjustments in groups.items():
            line = Line.create({
                'sheet_id': self.id,
                'employee_id': employee_id,
                'team_id': team_id or False,
                'source': 'manual',
                'company_id': company_id,
            })
            for adj in adjustments:
                reason_label = dict(
                    adj._fields['reason']._description_selection(self.env)
                ).get(adj.reason, '')
                desc = adj.description or reason_label
                if adj.adjustment_mode == 'percentage':
                    desc = f'{desc} ({adj.rate}%)'
                amount = adj.computed_amount
                DetailLine.create({
                    'line_id': line.id,
                    'event_type': 'manual',
                    'date': adj.date,
                    'description': desc,
                    'base_amount': amount,
                    'commission_amount': amount,
                    'fixed_amount': amount if adj.adjustment_mode == 'fixed' else 0.0,
                    'rate': adj.rate if adj.adjustment_mode == 'percentage' else 0.0,
                    'source': 'manual',
                })

    # =====================================================================
    # FASE 1: OBTENER DATOS (dispatch por data_source)
    # =====================================================================
    def _collect_data(self):
        """Despacha por data_source y llena commission.detail.line SIN regla."""
        self.ensure_one()
        active_teams = self.team_ids.filtered('commission_active')
        if not active_teams:
            _logger.warning(
                'Commissions[%s]: no hay equipos con commission_active=True.',
                self.name,
            )
            return
        _logger.info(
            'Commissions[%s]: obteniendo datos (data_source=%s) para %d equipos en %d cias',
            self.name, self.data_source, len(active_teams), len(self.company_ids),
        )
        if self.data_source == 'bank_paid':
            self._collect_bank_data(active_teams)
        elif self.data_source == 'invoice_paid':
            self._collect_invoice_data(active_teams, only_paid=True)
        elif self.data_source == 'invoice':
            self._collect_invoice_data(active_teams, only_paid=False)
        elif self.data_source == 'order':
            self._collect_order_data(active_teams)

    # ---------- bank_paid -----------------------------------------------------
    def _collect_bank_data(self, teams):
        invoices_data = self._scan_bank_statement_lines()
        _logger.info(
            'Commissions[%s]: scan banco -> %d facturas con cobro en periodo',
            self.name, len(invoices_data),
        )
        if not invoices_data:
            return
        for inv_id, data in invoices_data.items():
            inv = data['invoice']
            cobrado = data['cobrado']
            bsls = data['bsls']
            bsl = bsls[:1]
            if not cobrado or not inv.amount_total:
                continue
            fraccion = cobrado / inv.amount_total
            payment_tx = self._resolve_payment_transaction(inv)
            product_lines = inv.invoice_line_ids.filtered(
                lambda l: l.display_type == 'product' and l.sale_line_ids
            )
            for inv_line in product_lines:
                for sale_line in inv_line.sale_line_ids:
                    team = sale_line.order_id.team_id
                    if not team or team not in teams:
                        continue
                    base = inv_line.price_subtotal * fraccion
                    if base <= 0:
                        continue
                    employee_amounts = self._split_employee_amounts(team, sale_line, base)
                    for employee, employee_base in employee_amounts:
                        if not employee:
                            continue
                        self._emit_data_line(
                            event_type='bank_paid',
                            team=team, employee=employee, company=inv.company_id,
                            date_evt=bsl.date if bsl else inv.invoice_date,
                            sale_line=sale_line, inv_line=inv_line, invoice=inv,
                            bsl=bsl, payment_tx=payment_tx,
                            quantity=inv_line.quantity * fraccion,
                            base=employee_base,
                        )

    # ---------- invoice / invoice_paid ---------------------------------------
    def _collect_invoice_data(self, teams, only_paid):
        Move = self.env['account.move']
        if only_paid:
            paid_data = self._scan_bank_statement_lines()
            invoices_iter = [(d['invoice'], d['bsls'][:1]) for d in paid_data.values()]
        else:
            invoices = Move.search([
                ('move_type', '=', 'out_invoice'),
                ('state', '=', 'posted'),
                ('invoice_date', '>=', self.date_from),
                ('invoice_date', '<=', self.date_to),
                ('company_id', 'in', self.company_ids.ids),
            ])
            invoices_iter = [(inv, None) for inv in invoices]
        _logger.info(
            'Commissions[%s]: scan facturas (only_paid=%s) -> %d facturas',
            self.name, only_paid, len(invoices_iter),
        )
        for inv, bsl in invoices_iter:
            payment_tx = self._resolve_payment_transaction(inv)
            event_type = 'invoice_paid' if only_paid else 'invoice'
            date_evt = (bsl.date if bsl else None) or inv.invoice_date
            product_lines = inv.invoice_line_ids.filtered(
                lambda l: l.display_type == 'product' and l.sale_line_ids
            )
            for inv_line in product_lines:
                for sale_line in inv_line.sale_line_ids:
                    team = sale_line.order_id.team_id
                    if not team or team not in teams:
                        continue
                    base = inv_line.price_subtotal
                    if base <= 0:
                        continue
                    employee_amounts = self._split_employee_amounts(team, sale_line, base)
                    for employee, employee_base in employee_amounts:
                        if not employee:
                            continue
                        self._emit_data_line(
                            event_type=event_type,
                            team=team, employee=employee, company=inv.company_id,
                            date_evt=date_evt,
                            sale_line=sale_line, inv_line=inv_line, invoice=inv,
                            bsl=bsl, payment_tx=payment_tx,
                            quantity=inv_line.quantity,
                            base=employee_base,
                        )

    # ---------- order ---------------------------------------------------------
    def _collect_order_data(self, teams):
        SO = self.env['sale.order']
        orders = SO.search([
            ('state', '=', 'sale'),
            ('date_order', '>=', self.date_from),
            ('date_order', '<=', self.date_to),
            ('company_id', 'in', self.company_ids.ids),
            ('team_id', 'in', teams.ids),
        ])
        _logger.info(
            'Commissions[%s]: scan ordenes -> %d ordenes confirmadas',
            self.name, len(orders),
        )
        for order in orders:
            payment_tx = self._resolve_payment_transaction_so(order)
            invoice = order.invoice_ids[:1] if order.invoice_ids else self.env['account.move']
            date_evt = order.date_order.date() if order.date_order else False
            for sale_line in order.order_line:
                # En sale.order.line, display_type=False es la linea normal de producto.
                # display_type en ('line_section', 'line_note') son estructura, no comisionables.
                if sale_line.display_type:
                    continue
                if not sale_line.product_id:
                    continue
                if sale_line.price_subtotal <= 0:
                    continue
                team = order.team_id
                base = sale_line.price_subtotal
                employee_amounts = self._split_employee_amounts(team, sale_line, base)
                for employee, employee_base in employee_amounts:
                    if not employee:
                        continue
                    self._emit_data_line(
                        event_type='order',
                        team=team, employee=employee, company=order.company_id,
                        date_evt=date_evt,
                        sale_line=sale_line, inv_line=None, invoice=invoice,
                        bsl=None, payment_tx=payment_tx,
                        quantity=sale_line.product_uom_qty,
                        base=employee_base,
                    )

    # =====================================================================
    # FASE 2: APLICAR REGLAS A LAS DETAIL LINES OBTENIDAS
    # =====================================================================
    def _apply_rules(self):
        """Recorre detail lines (source='team') y aplica la regla matcheada.

        Si no hay regla, usa la tasa default del equipo. Las lineas manuales
        (source='manual') ya tienen su comision asignada y no se tocan.
        """
        self.ensure_one()
        rules = self._gather_applicable_rules()
        if not rules:
            _logger.info('Commissions[%s]: sin reglas aplicables para calcular.', self.name)

        # Agrupar reglas por (team_id, rule_type) para matching rapido.
        rules_index = defaultdict(lambda: self.env['commission.rate.rule'])
        for r in rules:
            rules_index[(r.team_id.id, r.rule_type)] |= r

        applied, defaulted = 0, 0
        for dline in self.detail_line_ids.filtered(lambda d: d.source == 'team'):
            team = dline.team_id
            if not team:
                continue
            # Buscar reglas que matcheen el event_type (con margin como variante de
            # bank_paid/invoice/etc., siguiendo el plan).
            candidates = rules_index.get((team.id, dline.event_type), self.env['commission.rate.rule'])
            # margin tambien es candidato para bank_paid/invoice/order si declara amount_basis=margin.
            margin_candidates = rules_index.get((team.id, 'margin'), self.env['commission.rate.rule'])
            candidates = candidates | margin_candidates

            rule = self.env['commission.rate.rule']._match(
                dline.product_id, team, dline.company_id, candidates=candidates,
            )
            base = dline.base_amount
            qty = dline.quantity
            if rule:
                # Si la regla es de margen, recalcula base = revenue - cost.
                if rule.rule_type == 'margin' or rule.amount_basis == 'margin':
                    base = max(0.0, dline.base_amount - dline.cost_amount)
                commission = rule.compute_commission(base, qty)
                dline.write({
                    'rule_id': rule.id,
                    'base_amount': base,
                    'rate': rule.rate if rule.computation_type == 'percentage' else 0.0,
                    'fixed_amount': rule.fixed_amount if rule.computation_type == 'fixed' else 0.0,
                    'commission_amount': commission,
                })
                applied += 1
            else:
                # Catch-all: usar tasa default del equipo.
                commission = team.get_default_commission(base, qty)
                dline.write({
                    'rule_id': False,
                    'rate': team.commission_rate if team.commission_computation == 'percentage' else 0.0,
                    'fixed_amount': team.commission_fixed_amount if team.commission_computation == 'fixed' else 0.0,
                    'commission_amount': commission,
                })
                defaulted += 1
        _logger.info(
            'Commissions[%s]: reglas aplicadas a %d lineas, default-team aplicado a %d.',
            self.name, applied, defaulted,
        )

    def _gather_applicable_rules(self):
        """Devuelve reglas activas que aplican a esta hoja.

        No filtramos por company_id de la regla porque el equipo puede operar
        en varias empresas (member_company_ids). El alcance multi-cia se decide
        en la hoja (`company_ids`) y se aplica al buscar las transacciones.
        Si una regla tiene company_id asignada, se respeta como filtro extra
        opcional.
        """
        self.ensure_one()
        active_teams = self.team_ids.filtered('commission_active')
        if not active_teams:
            return self.env['commission.rate.rule']
        rules = self.env['commission.rate.rule'].search([
            ('team_id', 'in', active_teams.ids),
            ('active', '=', True),
        ])
        rules = rules.filtered(
            lambda r: not r.company_id or r.company_id.id in self.company_ids.ids
        )
        return rules.filtered(lambda r: r._period_matches(self.date_from, self.date_to))

    # =====================================================================
    # Helpers de obtencion (compartidos)
    # =====================================================================
    def _emit_data_line(self, *, event_type, team, employee, company, date_evt,
                        sale_line, inv_line, invoice, bsl, payment_tx,
                        quantity, base):
        """Crea una commission.detail.line llena de snapshots pero SIN regla."""
        line = self._get_or_create_team_line(team, employee, company)
        task_snap = self._snapshot_task(sale_line) if sale_line else {}
        proj_snap = self._snapshot_project(sale_line) if sale_line else {}
        cost = self._compute_cost(sale_line, quantity) if sale_line else 0.0
        price_total = (
            inv_line.price_total if inv_line
            else (sale_line.price_total if sale_line else 0.0)
        )
        stripe_fee = self._stripe_fee_for_invoice(invoice, payment_tx) if invoice else 0.0

        order = sale_line.order_id if sale_line else False
        order_date = False
        if order and order.date_order:
            order_date = order.date_order.date() if hasattr(order.date_order, 'date') else order.date_order

        vals = {
            'line_id': line.id,
            'source': 'team',
            'event_type': event_type,
            'date': date_evt,
            'order_date': order_date,
            'partner_id': (order.partner_id.id if order else False)
                           or (invoice.partner_id.id if invoice else False),
            'description': (sale_line.name if sale_line else False)
                            or (inv_line.name if inv_line else ''),
            'sale_order_id': order.id if order else False,
            'sale_order_line_id': sale_line.id if sale_line else False,
            'product_id': (inv_line.product_id.id if inv_line else False)
                           or (sale_line.product_id.id if sale_line else False),
            'quantity': quantity or 0.0,
            'price_total': price_total,
            'cost_amount': cost,
            'invoice_id': invoice.id if invoice else False,
            'bank_statement_line_id': bsl.id if bsl else False,
            'payment_transaction_id': payment_tx.id if payment_tx else False,
            'stripe_fee': stripe_fee,
            'base_amount': base,
            # rule_id, rate, fixed_amount, commission_amount: vacios hasta _apply_rules.
            'commission_amount': 0.0,
            'rate': 0.0,
            'fixed_amount': 0.0,
        }
        vals.update(proj_snap)
        vals.update(task_snap)
        self.env['commission.detail.line'].create(vals)

    def _compute_cost(self, sale_line, quantity):
        product = sale_line.product_id
        if not product:
            return 0.0
        analytic_id = self._resolve_analytic_account(sale_line)
        if analytic_id:
            AnalyticLine = self.env['account.analytic.line']
            lines = AnalyticLine.search([
                ('account_id', '=', analytic_id.id),
                ('date', '>=', self.date_from),
                ('date', '<=', self.date_to),
            ])
            if lines:
                return abs(sum(lines.mapped('amount')))
        return (product.standard_price or 0.0) * (quantity or 0.0)

    def _resolve_analytic_account(self, sale_line):
        order = sale_line.order_id
        project = self.env['project.project'].search(
            [('reinvoiced_sale_order_id', '=', order.id)], limit=1,
        )
        if project and 'account_id' in project._fields and project.account_id:
            return project.account_id
        if project and 'analytic_account_id' in project._fields:
            return project.analytic_account_id
        return self.env['account.analytic.account']

    def _resolve_payment_transaction(self, invoice):
        if not invoice:
            return self.env['payment.transaction']
        if 'transaction_ids' in invoice._fields and invoice.transaction_ids:
            done = invoice.transaction_ids.filtered(lambda t: t.state == 'done')
            return done[:1] or invoice.transaction_ids[:1]
        orders = invoice.invoice_line_ids.sale_line_ids.order_id
        if orders:
            return self._resolve_payment_transaction_so(orders[:1])
        return self.env['payment.transaction']

    def _resolve_payment_transaction_so(self, order):
        if not order:
            return self.env['payment.transaction']
        PT = self.env['payment.transaction']
        tx = PT.search([
            ('sale_order_ids', 'in', order.ids),
            ('state', '=', 'done'),
            ('provider_code', '=', 'stripe'),
        ], order='create_date desc', limit=1)
        if tx:
            return tx
        return PT.search([
            ('sale_order_ids', 'in', order.ids),
            ('state', '=', 'done'),
        ], order='create_date desc', limit=1)

    def _snapshot_task(self, sale_line):
        task = self.env['project.task']
        if hasattr(sale_line, 'task_id') and sale_line.task_id:
            task = sale_line.task_id
        elif hasattr(sale_line, 'task_ids') and sale_line.task_ids:
            task = sale_line.task_ids[:1]
        if not task:
            return {}
        state_value = task.state if 'state' in task._fields else False
        return {
            'project_task_id': task.id,
            'task_state': TASK_STATE_LABELS.get(state_value, state_value or ''),
            'task_stage': task.stage_id.name if task.stage_id else '',
            'task_user_names': ', '.join(task.user_ids.mapped('name')) if task.user_ids else '',
            'task_date_last_stage_update': task.date_last_stage_update or False,
        }

    def _snapshot_project(self, sale_line):
        order = sale_line.order_id
        project = self.env['project.project'].search(
            [('reinvoiced_sale_order_id', '=', order.id)], limit=1,
        )
        analytic = self._resolve_analytic_account(sale_line)
        last_status = ''
        if project and 'last_update_status' in project._fields:
            last_status = project.last_update_status or ''
        return {
            'project_id': project.id if project else False,
            'analytic_account_id': analytic.id if analytic else False,
            'project_last_update_status': last_status,
        }

    def _stripe_fee_for_invoice(self, invoice, payment_tx):
        if not invoice:
            return 0.0
        if 'x_studio_fee_stripe' in invoice._fields and invoice.x_studio_fee_stripe:
            return invoice.x_studio_fee_stripe
        if payment_tx and 'stripe_fee' in payment_tx._fields:
            return payment_tx.stripe_fee or 0.0
        for so in invoice.invoice_line_ids.sale_line_ids.order_id:
            if 'x_studio_fee_stripe' in so._fields and so.x_studio_fee_stripe:
                return so.x_studio_fee_stripe
        return 0.0

    def _split_employee_amounts(self, team, sale_line, base):
        """Devuelve [(employee, base_asignado), ...] segun commission_split_method."""
        Employee = self.env['hr.employee']
        method = team.commission_split_method or 'seller'

        def by_seller():
            user = sale_line.order_id.user_id
            if not user:
                return []
            emp = Employee.search([
                ('user_id', '=', user.id),
                '|', ('company_id', 'in', self.company_ids.ids), ('company_id', '=', False),
            ], limit=1)
            return [(emp, base)] if emp else []

        if method == 'seller':
            return by_seller()
        if method == 'equal':
            members = team.member_ids
            employees = Employee.search([
                ('user_id', 'in', members.ids),
                '|', ('company_id', 'in', self.company_ids.ids), ('company_id', '=', False),
            ])
            if not employees:
                return by_seller()
            share = base / len(employees)
            return [(emp, share) for emp in employees]
        if method == 'task_assignee':
            task = self.env['project.task']
            if hasattr(sale_line, 'task_id') and sale_line.task_id:
                task = sale_line.task_id
            elif hasattr(sale_line, 'task_ids') and sale_line.task_ids:
                task = sale_line.task_ids[:1]
            if not task or not task.user_ids:
                return by_seller()
            employees = Employee.search([
                ('user_id', 'in', task.user_ids.ids),
                '|', ('company_id', 'in', self.company_ids.ids), ('company_id', '=', False),
            ])
            if not employees:
                return by_seller()
            share = base / len(employees)
            return [(emp, share) for emp in employees]
        return by_seller()

    def _get_or_create_team_line(self, team, employee, company):
        Line = self.env['commission.line']
        line = Line.search([
            ('sheet_id', '=', self.id),
            ('team_id', '=', team.id),
            ('employee_id', '=', employee.id),
            ('source', '=', 'team'),
        ], limit=1)
        if line:
            return line
        deduction = employee.commission_base_salary or team.commission_base_salary_deduction
        return Line.create({
            'sheet_id': self.id,
            'team_id': team.id,
            'employee_id': employee.id,
            'source': 'team',
            'company_id': company.id,
            'base_salary_deduction': deduction,
        })

    # ---------------------------------------------------------------------
    # Scan compartido de banco (bank_paid + invoice_paid)
    # ---------------------------------------------------------------------
    def _scan_bank_statement_lines(self):
        """Construye dict {invoice_id: {invoice, cobrado, bsls}} para el periodo."""
        self.ensure_one()
        AML = self.env['account.move.line']
        BSL = self.env['account.bank.statement.line']
        bsls = BSL.search([
            ('date', '>=', self.date_from),
            ('date', '<=', self.date_to),
            ('company_id', 'in', self.company_ids.ids),
            ('amount', '>', 0),
        ])
        if not bsls:
            return {}
        bsl_matching_lines = bsls.move_id.line_ids.filtered('matching_number')
        all_matching_numbers = list(set(bsl_matching_lines.mapped('matching_number')))
        if not all_matching_numbers:
            return {}
        inv_receivables = AML.search([
            ('matching_number', 'in', all_matching_numbers),
            ('account_id.account_type', '=', 'asset_receivable'),
            ('debit', '>', 0),
            ('move_id.move_type', '=', 'out_invoice'),
            ('move_id.state', '=', 'posted'),
            ('company_id', 'in', self.company_ids.ids),
        ])
        matching_to_invoice = {
            irl.matching_number: irl.move_id for irl in inv_receivables
        }
        invoices_data = {}
        for ml in bsl_matching_lines:
            mn = ml.matching_number
            inv = matching_to_invoice.get(mn)
            if not inv:
                continue
            bsl = ml.move_id.statement_line_id
            data = invoices_data.setdefault(inv.id, {
                'invoice': inv,
                'cobrado': 0.0,
                'bsls': BSL,
            })
            data['cobrado'] += ml.credit
            if bsl:
                data['bsls'] |= bsl
        return invoices_data

    # ---------------------------------------------------------------------
    # Smart buttons
    # ---------------------------------------------------------------------
    def action_open_lines(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Lineas - %s') % self.name,
            'res_model': 'commission.line',
            'view_mode': 'list,form',
            'domain': [('sheet_id', '=', self.id)],
            'context': {'default_sheet_id': self.id},
        }

    def action_open_detail_lines(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Lineas de detalle - %s') % self.name,
            'res_model': 'commission.detail.line',
            'view_mode': 'list,pivot,form',
            'domain': [('sheet_id', '=', self.id)],
        }
