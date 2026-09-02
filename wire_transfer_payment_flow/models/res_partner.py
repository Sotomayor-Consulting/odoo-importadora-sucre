from odoo import fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    wpf_project_creation_policy = fields.Selection(
        string='Project Creation Policy',
        selection=[
            ('on_confirm', 'On Sales Order Confirmation'),
            ('on_first_payment', 'On First Payment'),
            ('on_paid', 'When Invoice Is Fully Paid'),
        ],
        default='on_first_payment',
        help='Default policy used for sales orders of this customer.',
    )
