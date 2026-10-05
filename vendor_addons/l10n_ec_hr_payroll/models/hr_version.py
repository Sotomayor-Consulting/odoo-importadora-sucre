import base64

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools.mimetypes import guess_mimetype


class HRVersions(models.Model):
    _inherit = "hr.version"

    l10n_ec_quincena_fortnightly = fields.Monetary(
        string="Valor de la quincena",
        currency_field="currency_id",
        tracking=True,
        groups="hr_payroll.group_hr_payroll_user",
    )
    l10n_ec_13th_salary_accumulate = fields.Boolean(
        string="Acumula décimo tercero",
        default=True,
        tracking=True,
        groups="hr_payroll.group_hr_payroll_user",
        help="Marcado: se acumula y se paga hasta el 24 de diciembre. Desmarcado: se mensualiza en el rol.",
    )
    l10n_ec_14th_salary_accumulate = fields.Boolean(
        string="Acumula décimo cuarto",
        default=True,
        tracking=True,
        groups="hr_payroll.group_hr_payroll_user",
        help="Marcado: se acumula y se paga en la fecha de la región. Desmarcado: se mensualiza en el rol.",
    )
    l10n_ec_reserve_funds_accumulate = fields.Boolean(
        string="Acumula fondos de reserva",
        default=False,
        tracking=True,
        groups="hr_payroll.group_hr_payroll_user",
        help="Marcado: se depositan en el IESS. Desmarcado: se pagan mensualmente en el rol.",
    )

    l10n_ec_iess_entry_notice_file = fields.Binary(
        string="Aviso de entrada IESS",
        attachment=True,
        groups="hr_payroll.group_hr_payroll_user",
    )
    l10n_ec_iess_entry_notice_filename = fields.Char(
        string="Nombre del aviso de entrada",
        groups="hr_payroll.group_hr_payroll_user",
    )
    l10n_ec_iess_termination_notice_file = fields.Binary(
        string="Aviso de salida IESS",
        attachment=True,
        groups="hr_payroll.group_hr_payroll_user",
    )
    l10n_ec_iess_termination_notice_filename = fields.Char(
        string="Nombre del aviso de salida",
        groups="hr_payroll.group_hr_payroll_user",
    )

    l10n_ec_service_time = fields.Char(
        string="Tiempo de servicio",
        compute="_compute_l10n_ec_service_time",
        groups="hr_payroll.group_hr_payroll_user",
    )
    l10n_ec_active_days = fields.Integer(
        string="Días activo",
        compute="_compute_l10n_ec_service_time",
        groups="hr_payroll.group_hr_payroll_user",
    )
    l10n_ec_has_reserve_funds = fields.Boolean(
        string="Cobra fondos de reserva",
        compute="_compute_l10n_ec_service_time",
        groups="hr_payroll.group_hr_payroll_user",
        help="Derecho a fondos de reserva a partir del primer año de servicio (Art. 196 Ley de Seguridad Social).",
    )

    @api.constrains("l10n_ec_iess_entry_notice_file", "l10n_ec_iess_termination_notice_file")
    def _check_l10n_ec_iess_notice_pdf(self):
        """Los avisos del IESS solo aceptan PDF: se valida el contenido real del archivo,
        no la extension, porque el selector de archivos del navegador se puede saltar."""
        for version in self:
            for field_name in ("l10n_ec_iess_entry_notice_file", "l10n_ec_iess_termination_notice_file"):
                content = version[field_name]
                if content and guess_mimetype(base64.b64decode(content)) != "application/pdf":
                    raise ValidationError(_(
                        "El campo \"%(field)s\" solo acepta archivos PDF.",
                        field=version._fields[field_name].string,
                    ))

    def _l10n_ec_get_service_start_date(self):
        """Fecha inicial de servicio continuo: primer contrato del empleado,
        uniendo renovaciones sin interrupción (_get_first_contract_date)."""
        self.ensure_one()
        return (
            self.employee_id and self.employee_id._get_first_contract_date(no_gap=True)
            or self.contract_date_start
        )

    @api.depends("contract_date_start", "employee_id")
    def _compute_l10n_ec_service_time(self):
        today = fields.Date.today()
        for version in self:
            start_date = version._l10n_ec_get_service_start_date()
            if not start_date or start_date > today:
                version.l10n_ec_active_days = 0
                version.l10n_ec_service_time = "Sin fecha de inicio" if not start_date else "0 días"
                version.l10n_ec_has_reserve_funds = False
                continue
            delta = relativedelta(today, start_date)
            parts = []
            if delta.years:
                parts.append(f"{delta.years} {'año' if delta.years == 1 else 'años'}")
            if delta.months:
                parts.append(f"{delta.months} {'mes' if delta.months == 1 else 'meses'}")
            if delta.days or not parts:
                parts.append(f"{delta.days} {'día' if delta.days == 1 else 'días'}")
            version.l10n_ec_service_time = ", ".join(parts)
            version.l10n_ec_active_days = (today - start_date).days
            version.l10n_ec_has_reserve_funds = start_date + relativedelta(years=1) <= today
