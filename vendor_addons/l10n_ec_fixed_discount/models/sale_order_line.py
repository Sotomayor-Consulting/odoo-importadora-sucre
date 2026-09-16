from odoo import api, fields, models


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    discount_fixed = fields.Monetary(
        string='Descuento Fijo',
        currency_field='currency_id',
        compute='_compute_discount_fixed',
        inverse='_inverse_discount_fixed',
    )

    @api.depends('discount', 'price_unit', 'product_uom_qty')
    def _compute_discount_fixed(self):
        for line in self:
            currency = line.currency_id or line.order_id.company_id.currency_id
            base_price = line.price_unit * line.product_uom_qty
            line.discount_fixed = currency.round(base_price * line.discount / 100.0)

    def _inverse_discount_fixed(self):
        for line in self:
            currency = line.currency_id or line.order_id.company_id.currency_id
            base_price = line.price_unit * line.product_uom_qty
            if base_price:
                line.discount = currency.round(line.discount_fixed) / base_price * 100.0
            else:
                line.discount = 0.0