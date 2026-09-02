from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    _L10N_EC_RULE_ACCOUNT_MAP = {
        'l10n_ec_hr_payroll.l10n_ec_salary_rule_thirteenth_salary_accrual': (
            'l10n_ec_thirteenth_salary_expense_account_id',
            'l10n_ec_thirteenth_salary_provision_account_id',
        ),
        'l10n_ec_hr_payroll.l10n_ec_salary_rule_fourteenth_salary_accrual': (
            'l10n_ec_fourteenth_salary_expense_account_id',
            'l10n_ec_fourteenth_salary_provision_account_id',
        ),
        'l10n_ec_hr_payroll.l10n_ec_salary_rule_reserve_fund_accrual': (
            'l10n_ec_reserve_fund_expense_account_id',
            'l10n_ec_reserve_fund_provision_account_id',
        ),
        'l10n_ec_hr_payroll.l10n_ec_salary_rule_iess_employer_cost': (
            'l10n_ec_iess_employer_expense_account_id',
            'l10n_ec_iess_employer_liability_account_id',
        ),
    }

    l10n_ec_thirteenth_salary_expense_account_id = fields.Many2one(
        'account.account',
        string='Cuenta de gasto decimo tercero',
        domain="[('deprecated', '=', False)]",
    )
    l10n_ec_thirteenth_salary_provision_account_id = fields.Many2one(
        'account.account',
        string='Cuenta de provision decimo tercero',
        domain="[('deprecated', '=', False)]",
    )
    l10n_ec_fourteenth_salary_expense_account_id = fields.Many2one(
        'account.account',
        string='Cuenta de gasto decimo cuarto',
        domain="[('deprecated', '=', False)]",
    )
    l10n_ec_fourteenth_salary_provision_account_id = fields.Many2one(
        'account.account',
        string='Cuenta de provision decimo cuarto',
        domain="[('deprecated', '=', False)]",
    )
    l10n_ec_reserve_fund_expense_account_id = fields.Many2one(
        'account.account',
        string='Cuenta de gasto fondos de reserva',
        domain="[('deprecated', '=', False)]",
    )
    l10n_ec_reserve_fund_provision_account_id = fields.Many2one(
        'account.account',
        string='Cuenta de provision fondos de reserva',
        domain="[('deprecated', '=', False)]",
    )
    l10n_ec_iess_employer_expense_account_id = fields.Many2one(
        'account.account',
        string='Cuenta de gasto IESS patronal',
        domain="[('deprecated', '=', False)]",
    )
    l10n_ec_iess_employer_liability_account_id = fields.Many2one(
        'account.account',
        string='Cuenta por pagar IESS patronal',
        domain="[('deprecated', '=', False)]",
    )

    def write(self, vals):
        res = super().write(vals)
        tracked_fields = {
            field_name
            for account_fields in self._L10N_EC_RULE_ACCOUNT_MAP.values()
            for field_name in account_fields
        }
        if tracked_fields.intersection(vals):
            self._l10n_ec_sync_salary_rule_accounts()
        return res

    def _l10n_ec_sync_salary_rule_accounts(self):
        rule_refs = self._L10N_EC_RULE_ACCOUNT_MAP.keys()
        rules = {
            rule_ref: self.env.ref(rule_ref, raise_if_not_found=False)
            for rule_ref in rule_refs
        }
        for company in self:
            for rule_ref, (debit_field, credit_field) in self._L10N_EC_RULE_ACCOUNT_MAP.items():
                rule = rules[rule_ref]
                if not rule:
                    continue
                rule.with_company(company).write({
                    'account_debit': company[debit_field].id,
                    'account_credit': company[credit_field].id,
                    'not_computed_in_net': True,
                })
