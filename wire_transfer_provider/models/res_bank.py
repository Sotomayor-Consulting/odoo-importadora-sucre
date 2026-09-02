from odoo import fields, models


class ResBank(models.Model):
    _inherit = 'res.bank'

    wire_logo = fields.Image(
        string='Logo',
        max_width=256,
        max_height=256,
        help='Logo del banco que se muestra en el checkout de transferencia bancaria.',
    )
