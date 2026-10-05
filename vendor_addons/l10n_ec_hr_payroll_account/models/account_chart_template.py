from collections import defaultdict

from odoo import models


class AccountChartTemplate(models.AbstractModel):
    _inherit = "account.chart.template"

    def _configure_payroll_account_ec(self, companies):
        """Cuentas del plan estandar de Ecuador (l10n_ec) para las reglas de nomina.
        Convencion de hr_payroll_account: las deducciones tienen monto negativo, por eso su
        pasivo va en 'debit' (Odoo invierte el signo y lo registra al credito)."""
        account_codes = [
            '52010101',    # Sueldos y salarios
            '52010102',    # Horas extra
            '52010103',    # Bonificaciones
            '520110',      # Comisiones
            '52010201',    # Aporte patronal
            '52010202',    # Fondos de reserva
            '52010301',    # Decimo tercer sueldo
            '52010302',    # Decimo cuarto sueldo
            '52010408',    # Otros beneficios a empleados
            '11020701',    # Anticipo sueldos
            '11020705',    # Prestamos empleados
            '2105010102',  # Provision decimo tercero
            '2105010103',  # Provision decimo cuarto sierra
            '21070301',    # Prestamos quirografarios (IESS)
            '21070302',    # Prestamos hipotecarios (IESS)
            '21070303',    # Aportacion patronal al IESS
            '21070304',    # Aportacion personal al IESS
            '21070305',    # Fondos de reserva retenidos a empleados
            '21070401',    # Sueldos y salarios por pagar
        ]
        default_account = '52010101'
        rules_mapping = defaultdict(dict)

        def rule(xml_id):
            return self.env.ref(f'l10n_ec_hr_payroll.{xml_id}')

        # ==================================== #
        #     Ecuador: Nomina mensual empleado #
        # ==================================== #

        rules_mapping[rule('l10n_ec_rule_employee_basic')]['debit'] = '52010101'
        rules_mapping[rule('l10n_ec_rule_employee_ec_horas_supl')]['debit'] = '52010102'
        rules_mapping[rule('l10n_ec_rule_employee_ec_horas_extra')]['debit'] = '52010102'
        rules_mapping[rule('l10n_ec_rule_employee_ec_comision')]['debit'] = '520110'
        rules_mapping[rule('l10n_ec_rule_employee_ec_bono')]['debit'] = '52010103'
        rules_mapping[rule('l10n_ec_rule_employee_ec_ing_no_aport')]['debit'] = '52010408'

        rules_mapping[rule('l10n_ec_rule_employee_ec_iess_personal')]['debit'] = '21070304'
        rules_mapping[rule('l10n_ec_rule_employee_ec_prest_quiro')]['debit'] = '21070301'
        rules_mapping[rule('l10n_ec_rule_employee_ec_prest_hipo')]['debit'] = '21070302'
        rules_mapping[rule('l10n_ec_rule_employee_ec_descuento')]['debit'] = '11020705'
        rules_mapping[rule('l10n_ec_rule_employee_ec_quincena')]['debit'] = '11020701'
        rules_mapping[rule('l10n_ec_rule_employee_ec_anticipo')]['debit'] = '11020701'

        rules_mapping[rule('l10n_ec_rule_employee_ec_d13_mes')]['debit'] = '52010301'
        rules_mapping[rule('l10n_ec_rule_employee_ec_d14_mes')]['debit'] = '52010302'
        rules_mapping[rule('l10n_ec_rule_employee_ec_fr_mes')]['debit'] = '52010202'

        rules_mapping[rule('l10n_ec_rule_employee_ec_d13_prov')]['debit'] = '52010301'
        rules_mapping[rule('l10n_ec_rule_employee_ec_d13_prov')]['credit'] = '2105010102'
        rules_mapping[rule('l10n_ec_rule_employee_ec_d14_prov')]['debit'] = '52010302'
        rules_mapping[rule('l10n_ec_rule_employee_ec_d14_prov')]['credit'] = '2105010103'
        rules_mapping[rule('l10n_ec_rule_employee_ec_fr_prov')]['debit'] = '52010202'
        rules_mapping[rule('l10n_ec_rule_employee_ec_fr_prov')]['credit'] = '21070305'
        rules_mapping[rule('l10n_ec_rule_employee_ec_iess_patronal')]['debit'] = '52010201'
        rules_mapping[rule('l10n_ec_rule_employee_ec_iess_patronal')]['credit'] = '21070303'

        rules_mapping[rule('l10n_ec_rule_employee_net')]['credit'] = '21070401'

        # ==================================== #
        #     Ecuador: Nomina mensual pasante  #
        # ==================================== #

        rules_mapping[rule('l10n_ec_rule_intern_basic')]['debit'] = '52010101'
        rules_mapping[rule('l10n_ec_rule_intern_ec_comision')]['debit'] = '520110'
        rules_mapping[rule('l10n_ec_rule_intern_ec_quincena')]['debit'] = '11020701'
        rules_mapping[rule('l10n_ec_rule_intern_ec_anticipo')]['debit'] = '11020701'
        rules_mapping[rule('l10n_ec_rule_intern_ec_iess_patronal_pas')]['debit'] = '52010201'
        rules_mapping[rule('l10n_ec_rule_intern_ec_iess_patronal_pas')]['credit'] = '21070303'
        rules_mapping[rule('l10n_ec_rule_intern_net')]['credit'] = '21070401'

        self._configure_payroll_account(
            companies,
            "EC",
            account_codes=account_codes,
            rules_mapping=rules_mapping,
            default_account=default_account)
