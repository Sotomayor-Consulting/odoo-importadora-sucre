from dateutil.relativedelta import relativedelta

from odoo import api, fields, models


EC_PAYROLL_PAYMENT_SELECTION = [
    ('monthly', 'Monthly'),
    ('accumulated', 'Accumulated'),
]


class HrVersion(models.Model):
    _inherit = 'hr.version'

    l10n_ec_service_days = fields.Integer(
        string='Dias de antiguedad',
        compute='_compute_l10n_ec_service_time',
        groups='hr_payroll.group_hr_payroll_user',
    )
    l10n_ec_service_time_display = fields.Char(
        string='Tiempo laborado',
        compute='_compute_l10n_ec_service_time',
        groups='hr_payroll.group_hr_payroll_user',
    )

    l10n_ec_iess_affiliated = fields.Boolean(
        string='Afiliado al IESS',
        default=True,
        tracking=True,
        groups='hr_payroll.group_hr_payroll_user',
    )
    l10n_ec_thirteenth_salary_payment = fields.Selection(
        selection=EC_PAYROLL_PAYMENT_SELECTION,
        string='Pago de decimo tercero',
        default='accumulated',
        required=True,
        tracking=True,
        groups='hr_payroll.group_hr_payroll_user',
    )
    l10n_ec_fourteenth_salary_payment = fields.Selection(
        selection=EC_PAYROLL_PAYMENT_SELECTION,
        string='Pago de decimo cuarto',
        default='accumulated',
        required=True,
        tracking=True,
        groups='hr_payroll.group_hr_payroll_user',
    )
    l10n_ec_reserve_fund_payment = fields.Selection(
        selection=EC_PAYROLL_PAYMENT_SELECTION,
        string='Pago de fondos de reserva',
        default='accumulated',
        required=True,
        tracking=True,
        groups='hr_payroll.group_hr_payroll_user',
    )
    l10n_ec_apply_iess = fields.Boolean(
        string='Aplica IESS',
        default=True,
        tracking=True,
        groups='hr_payroll.group_hr_payroll_user',
    )
    l10n_ec_pay_quincena = fields.Boolean(
        string='Paga quincena',
        default=False,
        tracking=True,
        groups='hr_payroll.group_hr_payroll_user',
    )
    l10n_ec_quincena_amount = fields.Monetary(
        string='Valor de quincena',
        currency_field='currency_id',
        tracking=True,
        groups='hr_payroll.group_hr_payroll_user',
        help='Valor base de quincena usado como referencia para entradas de nomina.',
    )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('employee_id') and not vals.get('structure_type_id'):
                employee = self.env['hr.employee'].browse(vals['employee_id'])
                if employee.company_id.country_id.code == 'EC':
                    ec_type = self.env.ref(
                        'l10n_ec_hr_payroll.l10n_ec_payroll_structure_type_employee',
                        raise_if_not_found=False,
                    )
                    if ec_type:
                        vals['structure_type_id'] = ec_type.id
        return super().create(vals_list)

    @api.model
    def _get_whitelist_fields_from_template(self):
        fields_whitelist = super()._get_whitelist_fields_from_template() or []
        if self.env.company.country_id.code == 'EC':
            fields_whitelist += [
                'l10n_ec_iess_affiliated',
                'l10n_ec_thirteenth_salary_payment',
                'l10n_ec_fourteenth_salary_payment',
                'l10n_ec_reserve_fund_payment',
                'l10n_ec_apply_iess',
                'l10n_ec_pay_quincena',
                'l10n_ec_quincena_amount',
            ]
        return fields_whitelist

    @api.depends('contract_date_start', 'date_start')
    def _compute_l10n_ec_service_time(self):
        today = fields.Date.today()
        for version in self:
            start_date = version.contract_date_start or version.date_start
            if not start_date:
                version.l10n_ec_service_days = 0
                version.l10n_ec_service_time_display = 'Sin fecha de inicio'
                continue
            if start_date > today:
                version.l10n_ec_service_days = 0
                version.l10n_ec_service_time_display = '0 dias'
                continue
            delta = relativedelta(today, start_date)
            version.l10n_ec_service_days = (today - start_date).days
            parts = []
            if delta.years:
                parts.append(f"{delta.years} {'ano' if delta.years == 1 else 'anos'}")
            if delta.months:
                parts.append(f"{delta.months} {'mes' if delta.months == 1 else 'meses'}")
            if delta.days or not parts:
                parts.append(f"{delta.days} {'dia' if delta.days == 1 else 'dias'}")
            version.l10n_ec_service_time_display = ', '.join(parts)
