from odoo import _, fields, models
from odoo.exceptions import AccessError, UserError


class AccountOverdueBypassWizard(models.TransientModel):
    _name = 'account.overdue.bypass.wizard'
    _description = 'Overdue Invoices Control Bypass Wizard'

    res_model = fields.Selection(
        selection=[
            ('account.move', 'Customer Invoice'),
            ('sale.order', 'Sales Order'),
        ],
        string='Document Model',
        required=True,
        readonly=True,
    )
    res_id = fields.Integer(string='Document ID', required=True, readonly=True)
    partner_id = fields.Many2one('res.partner', string='Customer', readonly=True)
    overdue_message = fields.Char(string='Overdue Summary', readonly=True)
    reason = fields.Text(
        string='Bypass Reason',
        required=True,
        help="Mandatory reason explaining why this document is authorized despite the customer "
             "having overdue invoices.",
    )

    def action_confirm_bypass(self):
        self.ensure_one()
        if not self.env.user.has_group('account_overdue_control.group_overdue_control_bypass'):
            raise AccessError(_("You are not authorized to bypass the overdue invoices block."))

        reason = (self.reason or '').strip()
        if not reason:
            raise UserError(_("Please enter a valid reason to bypass the overdue invoices block."))

        record = self.env[self.res_model].browse(self.res_id).exists()
        if not record:
            raise UserError(_("The target document no longer exists."))

        record.write({
            'overdue_bypass_reason': reason,
            'overdue_bypass_user_id': self.env.user.id,
            'overdue_bypass_date': fields.Datetime.now(),
        })
        if self.res_model == 'account.move':
            record.action_post()
        elif self.res_model == 'sale.order':
            record.action_confirm()
        return {'type': 'ir.actions.act_window_close'}
