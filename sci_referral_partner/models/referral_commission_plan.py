from odoo import api, fields, models
from odoo.exceptions import ValidationError


class ReferralCommissionPlan(models.Model):
    _name = 'referral.commission.plan'
    _description = "Plan de comision de referidos"

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', string="Compañia")
    currency_id = fields.Many2one(
        'res.currency', compute='_compute_currency_id', store=True)
    commission_product_id = fields.Many2one(
        comodel_name='product.product',
        string="Producto de comision",
        help="Producto usado en la factura de proveedor de comisiones.")
    rule_ids = fields.One2many(
        comodel_name='referral.commission.rule',
        inverse_name='plan_id',
        string="Reglas",
        copy=True)

    @api.depends('company_id')
    def _compute_currency_id(self):
        for plan in self:
            plan.currency_id = (plan.company_id or self.env.company).currency_id

    def _match_rules(self, product):
        """Regla aplicable a un producto desde la tabla intermedia de reglas.

        Una regla aplica si su `product_id` es el producto, o si no tiene producto
        y su `category_id` es ancestro de la categoria del producto. Precedencia
        (mas especifico gana): servicio > categoria mas profunda > sequence.
        """
        self.ensure_one()
        parent_path = product.categ_id.parent_path or ''
        ancestor_ids = [int(c) for c in parent_path.split('/') if c]
        rules = self.env['referral.commission.rule'].search([
            ('plan_id', '=', self.id),
            '|',
                ('product_id', '=', product.id),
                '&', ('product_id', '=', False), ('category_id', 'in', ancestor_ids),
        ])
        if not rules:
            return rules
        rules = rules.sorted(
            key=lambda r: (
                1 if r.product_id else 0,
                len((r.category_id.parent_path or '').split('/')),
                -r.sequence,
            ),
            reverse=True,
        )
        return rules[:1]


class ReferralCommissionRule(models.Model):
    _name = 'referral.commission.rule'
    _description = "Regla de comision de referidos"
    _order = 'sequence, id'

    plan_id = fields.Many2one(
        comodel_name='referral.commission.plan',
        required=True, index=True, ondelete='cascade')
    company_id = fields.Many2one(related='plan_id.company_id', store=True)
    currency_id = fields.Many2one(related='plan_id.currency_id')
    sequence = fields.Integer(default=10)
    # Criterio: categoria O servicio (uno de los dos).
    category_id = fields.Many2one(
        comodel_name='product.category',
        string="Categoria", ondelete='cascade')
    product_id = fields.Many2one(
        comodel_name='product.product',
        string="Servicio", ondelete='cascade')
    # Comision: porcentaje O importe fijo, con tope opcional.
    commission_type = fields.Selection(
        selection=[('percentage', "Porcentaje"), ('fixed', "Importe fijo")],
        string="Tipo", required=True, default='percentage')
    rate = fields.Float(string="Tasa (%)", default=0.0)
    fixed_amount = fields.Monetary(string="Importe", currency_field='currency_id')
    max_commission = fields.Monetary(
        string="Comision maxima", currency_field='currency_id',
        help="Tope de la comision. 0 = sin tope.")

    _rate_range = models.Constraint(
        'CHECK(rate >= 0 AND rate <= 100)',
        "La tasa debe estar entre 0 y 100.")

    @api.constrains('category_id', 'product_id')
    def _check_criteria(self):
        for rule in self:
            if not rule.category_id and not rule.product_id:
                raise ValidationError(
                    "Cada regla debe indicar una categoria o un servicio.")

    def _compute_commission(self, base_amount):
        """Comision para una base dada, segun el tipo y el tope."""
        self.ensure_one()
        if self.commission_type == 'fixed':
            amount = self.fixed_amount
        else:
            amount = base_amount * self.rate / 100.0
        if self.max_commission:
            amount = min(amount, self.max_commission)
        return amount
