from odoo import api, fields, models


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    discount_fixed = fields.Monetary(
        string='Descuento Fijo',
        currency_field='currency_id',
        compute='_compute_discount_fixed',
        inverse='_inverse_discount_fixed',
    )

    @api.depends('discount', 'price_unit', 'quantity')
    def _compute_discount_fixed(self):
        for line in self:
            currency = line.currency_id or line.company_currency_id
            base_price = line.price_unit * line.quantity
            line.discount_fixed = currency.round(base_price * line.discount / 100.0)

    def _inverse_discount_fixed(self):
        for line in self:
            currency = line.currency_id or line.company_currency_id
            base_price = line.price_unit * line.quantity
            if base_price:
                line.discount = currency.round(line.discount_fixed) / base_price * 100.0
            else:
                line.discount = 0.0