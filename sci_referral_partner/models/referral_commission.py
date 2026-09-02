from odoo import fields, models


class ReferralCommission(models.Model):
    _name = 'referral.commission'
    _description = "Comision de referido devengada"
    _order = 'date desc, id desc'

    partner_id = fields.Many2one(
        comodel_name='res.partner', string="Partner", required=True, index=True,
        help="Partner referidor que gana la comision.")
    customer_id = fields.Many2one('res.partner', string="Cliente")
    invoice_id = fields.Many2one('account.move', string="Factura", index=True)
    invoice_line_id = fields.Many2one('account.move.line', string="Linea de factura")
    product_id = fields.Many2one('product.product', string="Servicio")
    company_id = fields.Many2one('res.company', string="Compañia")
    currency_id = fields.Many2one('res.currency', string="Moneda")
    date = fields.Date(string="Fecha")
    base_amount = fields.Monetary(string="Base", currency_field='currency_id')
    rate = fields.Float(string="Tasa (%)")
    commission_amount = fields.Monetary(string="Comision", currency_field='currency_id')
    is_clawback = fields.Boolean(string="Clawback")
    settlement_id = fields.Many2one(
        'referral.commission.settlement', string="Liquidacion",
        copy=False, index=True, ondelete='set null')
    state = fields.Selection(
        selection=[
            ('draft', "Devengada"),
            ('settled', "En liquidacion"),
            ('paid', "Pagada"),
        ],
        string="Estado", default='draft', required=True)
