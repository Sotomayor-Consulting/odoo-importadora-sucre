from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    l10n_ec_default_thirteenth_salary_payment = fields.Selection(
        related='company_id.l10n_ec_default_thirteenth_salary_payment',
        readonly=False,
        string='Pago predeterminado de decimo tercero',
    )
    l10n_ec_default_fourteenth_salary_payment = fields.Selection(
        related='company_id.l10n_ec_default_fourteenth_salary_payment',
        readonly=False,
        string='Pago predeterminado de decimo cuarto',
    )
    l10n_ec_default_reserve_fund_payment = fields.Selection(
        related='company_id.l10n_ec_default_reserve_fund_payment',
        readonly=False,
        string='Pago predeterminado de fondos de reserva',
    )
