from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    overdue_control_enabled = fields.Boolean(
        related='company_id.overdue_control_enabled',
        readonly=False,
    )
    overdue_grace_days = fields.Integer(
        related='company_id.overdue_grace_days',
        readonly=False,
    )
    overdue_tolerance = fields.Monetary(
        related='company_id.overdue_tolerance',
        currency_field='currency_id',
        readonly=False,
    )
    overdue_include_entries = fields.Boolean(
        related='company_id.overdue_include_entries',
        readonly=False,
    )
    overdue_cutoff_date = fields.Date(
        related='company_id.overdue_cutoff_date',
        readonly=False,
    )
