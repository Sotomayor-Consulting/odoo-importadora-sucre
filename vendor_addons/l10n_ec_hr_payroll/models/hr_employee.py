from odoo import fields, models


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    l10n_ec_iess_affiliated = fields.Boolean(
        readonly=False,
        related='version_id.l10n_ec_iess_affiliated',
        inherited=True,
        groups='hr_payroll.group_hr_payroll_user',
    )
    l10n_ec_thirteenth_salary_payment = fields.Selection(
        readonly=False,
        related='version_id.l10n_ec_thirteenth_salary_payment',
        inherited=True,
        groups='hr_payroll.group_hr_payroll_user',
    )
    l10n_ec_fourteenth_salary_payment = fields.Selection(
        readonly=False,
        related='version_id.l10n_ec_fourteenth_salary_payment',
        inherited=True,
        groups='hr_payroll.group_hr_payroll_user',
    )
    l10n_ec_reserve_fund_payment = fields.Selection(
        readonly=False,
        related='version_id.l10n_ec_reserve_fund_payment',
        inherited=True,
        groups='hr_payroll.group_hr_payroll_user',
    )
    l10n_ec_apply_iess = fields.Boolean(
        readonly=False,
        related='version_id.l10n_ec_apply_iess',
        inherited=True,
        groups='hr_payroll.group_hr_payroll_user',
    )
    l10n_ec_pay_quincena = fields.Boolean(
        readonly=False,
        related='version_id.l10n_ec_pay_quincena',
        inherited=True,
        groups='hr_payroll.group_hr_payroll_user',
    )
    l10n_ec_quincena_amount = fields.Monetary(
        readonly=False,
        related='version_id.l10n_ec_quincena_amount',
        inherited=True,
        groups='hr_payroll.group_hr_payroll_user',
    )
    l10n_ec_service_days = fields.Integer(
        related='version_id.l10n_ec_service_days',
        inherited=True,
        groups='hr_payroll.group_hr_payroll_user',
    )
    l10n_ec_service_time_display = fields.Char(
        related='version_id.l10n_ec_service_time_display',
        inherited=True,
        groups='hr_payroll.group_hr_payroll_user',
    )
