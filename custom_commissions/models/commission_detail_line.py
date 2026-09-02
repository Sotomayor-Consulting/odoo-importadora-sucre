from odoo import api, fields, models


class CommissionDetailLine(models.Model):
    _name = 'commission.detail.line'
    _description = 'Linea de detalle de comision (auditoria por transaccion)'
    _order = 'date desc, id desc'

    # ------------------------------------------------------------------
    # Vinculos estructurales
    # ------------------------------------------------------------------
    line_id = fields.Many2one(
        'commission.line',
        string='Linea',
        required=True,
        ondelete='cascade',
        index=True,
    )
    sheet_id = fields.Many2one(
        related='line_id.sheet_id',
        store=True,
        readonly=True,
        index=True,
    )
    employee_id = fields.Many2one(
        related='line_id.employee_id',
        store=True,
        readonly=True,
        index=True,
    )
    team_id = fields.Many2one(
        related='line_id.team_id',
        store=True,
        readonly=True,
    )
    user_id = fields.Many2one(
        related='line_id.user_id',
        store=True,
        readonly=True,
        index=True,
    )
    company_id = fields.Many2one(
        related='line_id.company_id',
        store=True,
        readonly=True,
        index=True,
    )
    currency_id = fields.Many2one(
        related='line_id.currency_id',
        readonly=True,
    )

    source = fields.Selection(
        [
            ('team', 'Equipo CRM'),
            ('product_role', 'Rol por producto'),
            ('manual', 'Ajuste manual'),
        ],
        required=True,
        default='team',
        index=True,
    )

    # ------------------------------------------------------------------
    # Tipo de evento (cobrado / facturado / vendido / etc.) que origino
    # esta linea — se setea durante action_collect_data antes de aplicar
    # cualquier regla. Es lo que el motor usa para matchear reglas.
    # ------------------------------------------------------------------
    event_type = fields.Selection(
        [
            ('bank_paid', 'Cobrado en banco'),
            ('invoice_paid', 'Factura pagada'),
            ('invoice', 'Factura emitida'),
            ('order', 'Orden confirmada'),
            ('qty_invoiced', 'Cantidad facturada'),
            ('qty_sold', 'Cantidad vendida'),
            ('task_done', 'Tarea cerrada'),
            ('manual', 'Ajuste manual'),
        ],
        string='Tipo evento',
        index=True,
        help='Que evento de negocio creo esta linea. Define que reglas matchean.',
    )

    # ------------------------------------------------------------------
    # Regla aplicada (se llena en action_calculate, posterior a obtener)
    # ------------------------------------------------------------------
    rule_id = fields.Many2one('commission.rate.rule', string='Regla aplicada')
    rule_type = fields.Selection(
        related='rule_id.rule_type',
        store=True,
        readonly=True,
        string='Tipo de regla',
    )
    is_calculated = fields.Boolean(
        string='Calculada',
        compute='_compute_is_calculated',
        store=True,
        help='True si la linea ya tiene comision calculada (rule_id o commission_amount asignados).',
    )

    @api.depends('rule_id', 'commission_amount')
    def _compute_is_calculated(self):
        for line in self:
            line.is_calculated = bool(line.rule_id) or bool(line.commission_amount)

    # ------------------------------------------------------------------
    # Fechas (n8n: FechaOrden, FechaFactura, FechaCobro)
    # ------------------------------------------------------------------
    date = fields.Date(
        string='Fecha evento',
        help='Fecha del evento que dispara la comision (cobro, factura, orden, tarea).',
    )
    order_date = fields.Date(string='Fecha orden')

    # ------------------------------------------------------------------
    # Cliente y producto
    # ------------------------------------------------------------------
    partner_id = fields.Many2one('res.partner', string='Cliente')
    description = fields.Char(string='Descripcion')

    sale_order_id = fields.Many2one('sale.order', string='Orden de venta')
    sale_order_line_id = fields.Many2one('sale.order.line', string='Linea de venta')

    product_id = fields.Many2one('product.product', string='Producto')
    quantity = fields.Float(string='Cantidad', digits='Product Unit of Measure')
    price_total = fields.Monetary(
        string='Precio total',
        help='Precio total de la linea con impuestos (snapshot).',
    )
    cost_amount = fields.Monetary(
        string='Costo',
        help='product.standard_price x cantidad, o suma de account.analytic.line si hay cuenta analitica.',
    )

    # ------------------------------------------------------------------
    # Factura y cobro (n8n: Factura, FacturaEstPago, Banco, FechaCobro,
    # PaymentTransactionId, PaymentIntentId)
    # ------------------------------------------------------------------
    invoice_id = fields.Many2one(
        'account.move',
        string='Factura',
        domain="[('move_type','in',['out_invoice','out_refund'])]",
    )
    bank_statement_line_id = fields.Many2one(
        'account.bank.statement.line',
        string='Linea de banco',
    )
    payment_transaction_id = fields.Many2one(
        'payment.transaction',
        string='Transaccion de pago',
    )
    stripe_fee = fields.Monetary(
        string='Fee Stripe',
        help='Snapshot del fee Stripe (x_studio_fee_stripe o balance_transaction.fee).',
    )

    # ------------------------------------------------------------------
    # Proyecto + tarea (snapshot del momento del calculo)
    # ------------------------------------------------------------------
    project_id = fields.Many2one('project.project', string='Proyecto')
    analytic_account_id = fields.Many2one(
        'account.analytic.account',
        string='Cuenta analitica',
        help='Cuenta analitica del proyecto, usada para margenes.',
    )
    project_last_update_status = fields.Char(
        string='Estado proyecto',
        help='Snapshot del project.last_update_status al momento del calculo.',
    )
    project_task_id = fields.Many2one('project.task', string='Tarea')
    task_state = fields.Char(string='Estado tarea')
    task_stage = fields.Char(string='Etapa tarea')
    task_user_names = fields.Char(string='Asignados')
    task_date_last_stage_update = fields.Datetime(string='Ultima act. tarea')

    # ------------------------------------------------------------------
    # Calculo
    # ------------------------------------------------------------------
    base_amount = fields.Monetary(string='Base')
    rate = fields.Float(string='Tasa (%)', digits=(5, 2))
    fixed_amount = fields.Monetary(string='Monto fijo')
    commission_amount = fields.Monetary(string='Comision')
