from odoo import fields, models


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    l10n_ec_quincena_fortnightly = fields.Monetary(
        readonly=False,
        related="version_id.l10n_ec_quincena_fortnightly",
        inherited=True,
        groups="hr_payroll.group_hr_payroll_user",
    )
    l10n_ec_13th_salary_accumulate = fields.Boolean(
        readonly=False,
        related="version_id.l10n_ec_13th_salary_accumulate",
        inherited=True,
        groups="hr_payroll.group_hr_payroll_user",
    )
    l10n_ec_14th_salary_accumulate = fields.Boolean(
        readonly=False,
        related="version_id.l10n_ec_14th_salary_accumulate",
        inherited=True,
        groups="hr_payroll.group_hr_payroll_user",
    )
    l10n_ec_reserve_funds_accumulate = fields.Boolean(
        readonly=False,
        related="version_id.l10n_ec_reserve_funds_accumulate",
        inherited=True,
        groups="hr_payroll.group_hr_payroll_user",
    )
    l10n_ec_iess_entry_notice_file = fields.Binary(
        readonly=False,
        related="version_id.l10n_ec_iess_entry_notice_file",
        inherited=True,
        groups="hr_payroll.group_hr_payroll_user",
    )
    l10n_ec_iess_entry_notice_filename = fields.Char(
        readonly=False,
        related="version_id.l10n_ec_iess_entry_notice_filename",
        inherited=True,
        groups="hr_payroll.group_hr_payroll_user",
    )
    l10n_ec_iess_termination_notice_file = fields.Binary(
        readonly=False,
        related="version_id.l10n_ec_iess_termination_notice_file",
        inherited=True,
        groups="hr_payroll.group_hr_payroll_user",
    )
    l10n_ec_iess_termination_notice_filename = fields.Char(
        readonly=False,
        related="version_id.l10n_ec_iess_termination_notice_filename",
        inherited=True,
        groups="hr_payroll.group_hr_payroll_user",
    )
    l10n_ec_service_time = fields.Char(
        related="version_id.l10n_ec_service_time",
        inherited=True,
        groups="hr_payroll.group_hr_payroll_user",
    )
    l10n_ec_active_days = fields.Integer(
        related="version_id.l10n_ec_active_days",
        inherited=True,
        groups="hr_payroll.group_hr_payroll_user",
    )
    l10n_ec_has_reserve_funds = fields.Boolean(
        related="version_id.l10n_ec_has_reserve_funds",
        inherited=True,
        groups="hr_payroll.group_hr_payroll_user",
    )
