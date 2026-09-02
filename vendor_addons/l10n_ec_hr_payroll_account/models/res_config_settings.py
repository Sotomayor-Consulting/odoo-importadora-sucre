from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    l10n_ec_thirteenth_salary_expense_account_id = fields.Many2one(
        related='company_id.l10n_ec_thirteenth_salary_expense_account_id',
        readonly=False,
        string='Cuenta de gasto decimo tercero',
    )
    l10n_ec_thirteenth_salary_provision_account_id = fields.Many2one(
        related='company_id.l10n_ec_thirteenth_salary_provision_account_id',
        readonly=False,
        string='Cuenta de provision decimo tercero',
    )
    l10n_ec_fourteenth_salary_expense_account_id = fields.Many2one(
        related='company_id.l10n_ec_fourteenth_salary_expense_account_id',
        readonly=False,
        string='Cuenta de gasto decimo cuarto',
    )
    l10n_ec_fourteenth_salary_provision_account_id = fields.Many2one(
        related='company_id.l10n_ec_fourteenth_salary_provision_account_id',
        readonly=False,
        string='Cuenta de provision decimo cuarto',
    )
    l10n_ec_reserve_fund_expense_account_id = fields.Many2one(
        related='company_id.l10n_ec_reserve_fund_expense_account_id',
        readonly=False,
        string='Cuenta de gasto fondos de reserva',
    )
    l10n_ec_reserve_fund_provision_account_id = fields.Many2one(
        related='company_id.l10n_ec_reserve_fund_provision_account_id',
        readonly=False,
        string='Cuenta de provision fondos de reserva',
    )
    l10n_ec_iess_employer_expense_account_id = fields.Many2one(
        related='company_id.l10n_ec_iess_employer_expense_account_id',
        readonly=False,
        string='Cuenta de gasto IESS patronal',
    )
    l10n_ec_iess_employer_liability_account_id = fields.Many2one(
        related='company_id.l10n_ec_iess_employer_liability_account_id',
        readonly=False,
        string='Cuenta por pagar IESS patronal',
    )
