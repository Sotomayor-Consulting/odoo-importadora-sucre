from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


RULE_TYPE_SELECTION = [
    ('bank_paid', 'Cobrado en banco'),
    ('invoice_paid', 'Factura pagada'),
    ('invoice', 'Importe facturado'),
    ('order', 'Importe vendido (orden confirmada)'),
    ('margin', 'Margen'),
    ('qty_invoiced', 'Cantidad facturada'),
    ('qty_sold', 'Cantidad vendida'),
    ('task_done', 'Tarea cerrada (Operaciones)'),
]


class CommissionRateRule(models.Model):
    _name = 'commission.rate.rule'
    _description = 'Regla de comision'
    _order = 'sequence, id'

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)
    sequence = fields.Integer(default=10)

    team_id = fields.Many2one(
        'crm.team',
        string='Equipo',
        required=True,
        ondelete='cascade',
        index=True,
    )
    company_id = fields.Many2one(
        'res.company',
        string='Compania',
        index=True,
        help=(
            'Si se deja vacio, la regla aplica a TODAS las companias del equipo '
            '(util cuando el equipo opera en varias empresas). Si se asigna una '
            'compania, la regla solo aplica a transacciones de esa compania.'
        ),
    )
    currency_id = fields.Many2one(
        'res.currency',
        compute='_compute_currency_id',
        store=True,
        readonly=True,
    )

    @api.depends('company_id', 'team_id')
    def _compute_currency_id(self):
        for rule in self:
            company = rule.company_id or rule.team_id.company_id or self.env.company
            rule.currency_id = company.currency_id

    # ------------------------------------------------------------------
    # Frecuencia y tipo (lo nuevo)
    # ------------------------------------------------------------------
    frequency = fields.Selection(
        [
            ('monthly', 'Mensual'),
            ('quarterly', 'Trimestral'),
            ('yearly', 'Anual'),
        ],
        string='Frecuencia',
        default='monthly',
        required=True,
        help=(
            'Periodicidad en la que la regla aplica. El motor descarta la regla '
            'si el rango de la hoja no encaja con la frecuencia '
            '(ver _period_matches).'
        ),
    )
    rule_type = fields.Selection(
        RULE_TYPE_SELECTION,
        string='Tipo',
        default='bank_paid',
        required=True,
        help=(
            'Que evento dispara la comision y que base se usa.\n'
            '- Cobrado en banco: cobro conciliado en el periodo.\n'
            '- Factura pagada: factura con pago en el periodo (base completa).\n'
            '- Importe facturado: factura emitida en el periodo.\n'
            '- Importe vendido: orden confirmada en el periodo.\n'
            '- Margen: ingreso - costo analitico del proyecto.\n'
            '- Cantidad facturada / vendida: tasa por unidad.\n'
            '- Tarea cerrada: Operaciones (Fase 4).'
        ),
    )
    amount_basis = fields.Selection(
        [
            ('revenue', 'Valor de venta (pre-impuesto)'),
            ('margin', 'Margen (ingreso - costos)'),
        ],
        string='Base monetaria',
        default='revenue',
        help=(
            'Solo aplica para los tipos basados en importe (bank/invoice/order).'
            ' En margen y qty_* el motor calcula la base segun el tipo.'
        ),
    )

    # ------------------------------------------------------------------
    # Criterios
    # ------------------------------------------------------------------
    product_ids = fields.Many2many(
        'product.product',
        'commission_rate_rule_product_rel',
        'rule_id',
        'product_id',
        string='Productos',
        help='Si se define, la regla aplica solo a estos productos.',
    )
    product_category_ids = fields.Many2many(
        'product.category',
        'commission_rate_rule_categ_rel',
        'rule_id',
        'categ_id',
        string='Categorias',
        help='Aplica si la categoria del producto (o alguna padre) esta en la lista.',
    )

    # ------------------------------------------------------------------
    # Calculo
    # ------------------------------------------------------------------
    computation_type = fields.Selection(
        [
            ('percentage', 'Porcentaje'),
            ('fixed', 'Monto fijo'),
        ],
        string='Tipo de calculo',
        default='percentage',
        required=True,
    )
    rate = fields.Float(string='Tasa (%)', digits=(5, 2))
    fixed_amount = fields.Monetary(
        string='Monto fijo',
        help=(
            'Para reglas qty_*: monto fijo por unidad. '
            'Para el resto: monto fijo por log emitido.'
        ),
    )

    # Visualizacion de vendedores del equipo (no se usa en el calculo,
    # el reparto lo decide team.commission_split_method).
    seller_user_ids = fields.Many2many(
        'res.users',
        related='team_id.member_ids',
        string='Vendedores del equipo',
        readonly=True,
    )

    notes = fields.Char(string='Notas')

    # ------------------------------------------------------------------
    # Constraints
    # ------------------------------------------------------------------
    @api.constrains('computation_type', 'rate', 'fixed_amount')
    def _check_amounts(self):
        for rule in self:
            if rule.computation_type == 'percentage' and rule.rate < 0:
                raise ValidationError(_('La tasa porcentual no puede ser negativa.'))
            if rule.computation_type == 'fixed' and rule.fixed_amount < 0:
                raise ValidationError(_('El monto fijo no puede ser negativo.'))

    @api.constrains('rule_type', 'computation_type', 'fixed_amount', 'rate')
    def _check_qty_rules(self):
        for rule in self:
            if rule.rule_type in ('qty_invoiced', 'qty_sold'):
                # tipico: X $ por unidad. Si es %, advertencia: el motor lo permite
                # pero requiere que la linea tenga price_subtotal_unit.
                if rule.computation_type == 'fixed' and rule.fixed_amount <= 0:
                    raise ValidationError(_(
                        'Las reglas por cantidad con monto fijo requieren un fixed_amount > 0.'
                    ))

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _category_chain(self, product):
        chain = []
        cat = product.categ_id
        while cat:
            chain.append(cat.id)
            cat = cat.parent_id
        return chain

    @api.model
    def _match(self, product, team, company=None, candidates=None):
        """Devuelve la regla aplicable de mayor prioridad para (producto, equipo, cia).

        Si `candidates` se pasa (recordset de reglas pre-filtradas, p.ej. por
        rule_type y frecuencia), busca dentro de ese conjunto. Sin candidates,
        busca todas las reglas activas del equipo/compania.

        Precedencia:
          1. Regla con product_ids que contiene el producto.
          2. Regla con product_category_ids que cubre la categoria del producto.
          3. Regla sin criterios (catch-all).
        Dentro del mismo nivel gana la de menor sequence.
        """
        if not product or not team:
            return None
        if candidates is None:
            domain = [('team_id', '=', team.id), ('active', '=', True)]
            candidates = self.search(domain)
            if company:
                # Si la regla tiene compania asignada, debe coincidir; si no, aplica siempre.
                candidates = candidates.filtered(
                    lambda r: not r.company_id or r.company_id.id == company.id
                )
        else:
            # Aseguramos orden por sequence dentro del set pasado.
            candidates = candidates.sorted(key=lambda r: (r.sequence, r.id))

        cat_chain = set(self._category_chain(product))

        for rule in candidates:
            if product in rule.product_ids:
                return rule
        for rule in candidates:
            if (
                not rule.product_ids
                and rule.product_category_ids
                and cat_chain & set(rule.product_category_ids.ids)
            ):
                return rule
        for rule in candidates:
            if not rule.product_ids and not rule.product_category_ids:
                return rule
        return None

    def _period_matches(self, date_from, date_to):
        """True si el rango [date_from, date_to] encaja con la frecuencia de la regla.

        - monthly: siempre aplica (cualquier rango es valido; pensado para hojas mensuales).
        - quarterly: el rango debe coincidir con un trimestre completo
          (Q1: ene-mar, Q2: abr-jun, Q3: jul-sep, Q4: oct-dic).
        - yearly: el rango debe cubrir un ano completo (1 enero a 31 diciembre).

        Esta verificacion es relativamente estricta; se puede flexibilizar a futuro
        (p.ej. permitir trimestral en hojas mensuales con prorrateo).
        """
        self.ensure_one()
        if not date_from or not date_to:
            return False
        if self.frequency == 'monthly':
            return True
        if self.frequency == 'quarterly':
            valid = {
                (1, 3),   # Q1: ene 1 – mar 31
                (4, 6),   # Q2: abr 1 – jun 30
                (7, 9),   # Q3: jul 1 – sep 30
                (10, 12), # Q4: oct 1 – dic 31
            }
            return (
                date_from.day == 1
                and date_to.day in (28, 29, 30, 31)
                and (date_from.month, date_to.month) in valid
                and date_from.year == date_to.year
            )
        if self.frequency == 'yearly':
            return (
                date_from.day == 1 and date_from.month == 1
                and date_to.day == 31 and date_to.month == 12
                and date_from.year == date_to.year
            )
        return False

    def compute_commission(self, base_amount, quantity=None):
        """Aplica la regla. Devuelve el monto de comision.

        - percentage: base_amount * rate / 100.
        - fixed con quantity (reglas qty_*): fixed_amount * quantity.
        - fixed sin quantity: fixed_amount tal cual (1 vez por log).
        """
        self.ensure_one()
        if self.computation_type == 'fixed':
            if quantity is not None:
                return self.fixed_amount * quantity
            return self.fixed_amount
        # percentage
        return base_amount * (self.rate / 100.0)
