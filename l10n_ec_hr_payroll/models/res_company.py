from odoo import fields, models

from .hr_version import EC_PAYROLL_PAYMENT_SELECTION


class ResCompany(models.Model):
    _inherit = 'res.company'

    l10n_ec_default_thirteenth_salary_payment = fields.Selection(
        selection=EC_PAYROLL_PAYMENT_SELECTION,
        string='Pago predeterminado de decimo tercero',
        default='accumulated',
        required=True,
    )
    l10n_ec_default_fourteenth_salary_payment = fields.Selection(
        selection=EC_PAYROLL_PAYMENT_SELECTION,
        string='Pago predeterminado de decimo cuarto',
        default='accumulated',
        required=True,
    )
    l10n_ec_default_reserve_fund_payment = fields.Selection(
        selection=EC_PAYROLL_PAYMENT_SELECTION,
        string='Pago predeterminado de fondos de reserva',
        default='accumulated',
        required=True,
    )
