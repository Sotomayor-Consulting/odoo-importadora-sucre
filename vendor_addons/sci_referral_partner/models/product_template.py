from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    referral_commissionable = fields.Boolean(
        string="Comisionable a referidos",
        default=True,
        help="Si se desmarca, las lineas de este producto no entran en la base de"
             " comision de referidos (p. ej. tasas/fees gubernamentales, bancarios"
             " o costos de terceros).")
