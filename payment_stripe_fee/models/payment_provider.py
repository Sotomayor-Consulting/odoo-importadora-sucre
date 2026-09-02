from odoo import fields, models

class PaymentProvider(models.Model):
    _inherit = 'payment.provider'

    stripe_fee_percentage = fields.Float(string="Stripe Fee (%)")
    stripe_fee_fixed = fields.Float(string="Stripe Fixed Fee")
    stripe_fee_product_id = fields.Many2one(
        comodel_name='product.product',
        string='Stripe Fee Product',
        domain="[('sale_ok', '=', True), ('type', '=', 'service')]",
        help='Producto usado para la linea del fee en la orden de venta. Su cuenta de '
             'ingreso (configurada en el producto) recibe el fee al cobrar una factura.',
    )
