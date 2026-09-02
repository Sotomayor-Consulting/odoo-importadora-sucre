from dateutil.relativedelta import relativedelta

from odoo import fields, models


class HrPayslip(models.Model):
    _inherit = 'hr.payslip'

    def _l10n_ec_get_base_wage(self, version):
        self.ensure_one()
        wage = version.wage if version else 0.0
        return wage if wage > 0 else self._rule_parameter('EC_SBU')

    def _l10n_ec_get_reserve_fund_eligibility_date(self, version):
        self.ensure_one()
        if not version:
            return False
        start_date = version.contract_date_start or version.date_start
        return start_date + relativedelta(years=1) if start_date else False

    def _l10n_ec_get_period_day_count(self):
        self.ensure_one()
        if not self.date_from or not self.date_to or self.date_to < self.date_from:
            return 0
        return (self.date_to - self.date_from).days + 1

    def _l10n_ec_get_reserve_fund_eligible_days(self, version):
        self.ensure_one()
        eligibility_date = self._l10n_ec_get_reserve_fund_eligibility_date(version)
        if not eligibility_date or not self.date_from or not self.date_to:
            return 0
        if eligibility_date > self.date_to:
            return 0
        eligible_from = max(self.date_from, eligibility_date)
        return (self.date_to - eligible_from).days + 1

    def _l10n_ec_get_reserve_fund_prorated_amount(self, version):
        self.ensure_one()
        period_days = self._l10n_ec_get_period_day_count()
        eligible_days = self._l10n_ec_get_reserve_fund_eligible_days(version)
        if not period_days or not eligible_days:
            return 0.0
        return self._l10n_ec_get_base_wage(version) / 12.0 * eligible_days / period_days

    def _l10n_ec_get_input_amount(self, code):
        self.ensure_one()
        line = self.input_line_ids.filtered(lambda input_line: input_line.input_type_id.code == code)[:1]
        return line.amount if line else 0.0

    def _l10n_ec_get_quincena_amount(self, version):
        self.ensure_one()
        override_amount = self._l10n_ec_get_input_amount('EC_QUINCENA_AMOUNT_OVERRIDE')
        version_amount = version.l10n_ec_quincena_amount if version else 0.0
        return override_amount or version_amount

    def _l10n_ec_is_monthly_payment(self, version, field_name):
        self.ensure_one()
        return bool(version) and version[field_name] == 'monthly'

    def _l10n_ec_is_accumulated_payment(self, version, field_name):
        self.ensure_one()
        return bool(version) and version[field_name] == 'accumulated'
