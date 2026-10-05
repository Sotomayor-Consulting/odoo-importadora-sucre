from calendar import monthrange

from dateutil.relativedelta import relativedelta

from odoo import api, models
from odoo.tools import float_round

# Ecuador liquida la nomina con mes comercial de 30 dias.
EC_COMMERCIAL_MONTH_DAYS = 30
# Horas mensuales de una jornada de 40 horas semanales (base del valor hora, Art. 55 Codigo del Trabajo).
EC_MONTHLY_HOURS = 240


class HrPayslip(models.Model):
    _inherit = "hr.payslip"

    def _get_payslip_line_total(self, amount, quantity, rate, rule):
        """Redondea cada linea a centavos (HALF-UP) en estructuras de Ecuador, igual que la
        localizacion suiza redondea a 5 centavos. Asi el neto es exactamente la suma de las
        lineas que se muestran y cuadra con la planilla del IESS y la transferencia."""
        total = super()._get_payslip_line_total(amount, quantity, rate, rule)
        if rule.struct_id.country_id.code != "EC":
            return total
        return float_round(total, precision_rounding=self.currency_id.rounding, rounding_method="HALF-UP")

    @api.model
    def _l10n_ec_commercial_days(self, date_from, date_to):
        """Dias comerciales entre dos fechas (ambas incluidas), contando cada mes como 30 dias:
        un mes completo son 30 dias aunque tenga 28 o 31, e ingresar el 15 da 16 dias."""
        if not date_from or not date_to or date_from > date_to:
            return 0
        days = 0
        current = date_from
        while current <= date_to:
            month_end = current.replace(day=monthrange(current.year, current.month)[1])
            end = min(date_to, month_end)
            start_day = min(current.day, EC_COMMERCIAL_MONTH_DAYS)
            end_day = EC_COMMERCIAL_MONTH_DAYS if end == month_end else min(end.day, EC_COMMERCIAL_MONTH_DAYS)
            days += max(end_day - start_day + 1, 0)
            current = end + relativedelta(days=1)
        return days

    def _l10n_ec_get_contract_period(self):
        """Parte del periodo del recibo cubierta por el contrato."""
        self.ensure_one()
        version = self.version_id
        start = max(self.date_from, version.contract_date_start or self.date_from)
        end = min(self.date_to, version.contract_date_end or self.date_to)
        return start, end

    def _l10n_ec_get_contract_days(self):
        self.ensure_one()
        return self._l10n_ec_commercial_days(*self._l10n_ec_get_contract_period())

    def _l10n_ec_get_unpaid_days(self):
        """Dias sin sueldo: la entrada manual EC_DIAS_NO_PAGADOS y, si la estructura usa
        entradas de trabajo, las ausencias de tipos marcados como no pagados."""
        self.ensure_one()
        manual_days = sum(self.input_line_ids.filtered(lambda line: line.code == "EC_DIAS_NO_PAGADOS").mapped("amount"))
        work_entry_days = sum(
            line.number_of_days for line in self.worked_days_line_ids
            if not line.is_paid and line.code != "OUT"
        )
        return manual_days + work_entry_days

    def _l10n_ec_get_paid_days(self):
        self.ensure_one()
        return max(self._l10n_ec_get_contract_days() - self._l10n_ec_get_unpaid_days(), 0)

    def _l10n_ec_get_paid_ratio(self):
        """Fraccion del mes comercial que se paga (1.0 = mes completo)."""
        self.ensure_one()
        return self._l10n_ec_get_paid_days() / EC_COMMERCIAL_MONTH_DAYS

    def _l10n_ec_get_daily_wage(self):
        self.ensure_one()
        return self.version_id.wage / EC_COMMERCIAL_MONTH_DAYS

    def _l10n_ec_get_hourly_wage(self):
        self.ensure_one()
        return self.version_id.wage / EC_MONTHLY_HOURS

    def _l10n_ec_get_reserve_funds_ratio(self):
        """Fraccion del periodo con derecho a fondos de reserva: desde el dia en que se cumple
        el primer año de servicio continuo (Art. 196 Ley de Seguridad Social).
        Se calcula con las fechas del recibo, no con la fecha de hoy."""
        self.ensure_one()
        service_start = self.version_id._l10n_ec_get_service_start_date()
        contract_days = self._l10n_ec_get_contract_days()
        if not service_start or not contract_days:
            return 0.0
        start, end = self._l10n_ec_get_contract_period()
        eligible_from = max(start, service_start + relativedelta(years=1))
        eligible_days = self._l10n_ec_commercial_days(eligible_from, end)
        return eligible_days / contract_days
