from odoo import fields, models


class ResPartner(models.Model):
    _inherit = "res.partner"
    
    _rec_names_search = [
        "complete_name",
        "email",
        "ref",
        "vat",
        "company_registry",
        "comercial",
    ]

    comercial = fields.Char(
        string="Nombre comercial",
        index="trigram",
        help="Nombre comercial del contacto, distinto de la razon social.",
    )
