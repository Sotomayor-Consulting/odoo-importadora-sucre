from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError


class AccountMove(models.Model):
    _inherit = 'account.move'

    overdue_control_blocked = fields.Boolean(
        compute='_compute_overdue_control',
        string='Blocked by Overdue Invoices',
    )
    overdue_control_message = fields.Char(
        compute='_compute_overdue_control',
        string='Overdue Control Message',
    )
    overdue_control_can_view_invoices = fields.Boolean(
        compute='_compute_overdue_control_can_view_invoices',
    )
    overdue_bypass_reason = fields.Text(
        string='Overdue Bypass Reason',
        copy=False,
        readonly=True,
    )
    overdue_bypass_user_id = fields.Many2one(
        'res.users',
        string='Overdue Bypass Approved By',
        copy=False,
        readonly=True,
    )
    overdue_bypass_date = fields.Datetime(
        string='Overdue Bypass Date',
        copy=False,
        readonly=True,
    )

    @api.depends('partner_id', 'company_id', 'move_type', 'state')
    def _compute_overdue_control(self):
        candidates = self.filtered(
            lambda m: m.move_type == 'out_invoice' and m.state == 'draft' and m.partner_id
        )
        for move in self - candidates:
            move.overdue_control_blocked = False
            move.overdue_control_message = ''
        if not candidates:
            return

        pairs = [
            (m.partner_id._origin.commercial_partner_id, m.company_id._origin)
            for m in candidates
        ]
        statuses = self.env['res.partner']._get_overdue_control_status_batch(
            pairs,
            exclude_move_ids=candidates._origin.ids,
        )
        for move in candidates:
            key = (move.partner_id._origin.commercial_partner_id.id, move.company_id._origin.id)
            status = statuses.get(key)
            if status and status['blocked']:
                move.overdue_control_blocked = True
                move.overdue_control_message = status['message']
            else:
                move.overdue_control_blocked = False
                move.overdue_control_message = ''

    def _compute_overdue_control_can_view_invoices(self):
        can_view = (
            self.env.user.has_group('account.group_account_readonly')
            or self.env.user.has_group('account.group_account_invoice')
        )
        self.overdue_control_can_view_invoices = can_view

    def _get_overdue_control_status(self):
        self.ensure_one()
        if self.move_type != 'out_invoice' or self.state != 'draft' or not self.partner_id:
            return self.env['res.partner']._empty_overdue_status()
        return self.partner_id._get_overdue_control_status(
            self.company_id,
            exclude_ids=self._origin.ids,
        )

    def action_view_overdue_invoices(self):
        self.ensure_one()
        status = self._get_overdue_control_status()
        return self.partner_id._action_view_overdue_invoices(
            status['invoices'],
            lines=status['lines'],
            has_entries=status['has_entries'],
        )

    def action_open_overdue_bypass_wizard(self):
        self.ensure_one()
        if not self.env.user.has_group('account_overdue_control.group_overdue_control_bypass'):
            raise AccessError(_("You are not authorized to bypass the overdue invoices block."))
        status = self._get_overdue_control_status()
        if not status['blocked']:
            raise UserError(_("This invoice is not currently blocked by overdue invoices."))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Bypass Overdue Invoices Block'),
            'res_model': 'account.overdue.bypass.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_res_model': 'account.move',
                'default_res_id': self.id,
                'default_partner_id': self.partner_id.commercial_partner_id.id,
                'default_overdue_message': status['message'],
            },
        }

    def button_draft(self):
        res = super().button_draft()
        self.filtered('overdue_bypass_reason').write({
            'overdue_bypass_reason': False,
            'overdue_bypass_user_id': False,
            'overdue_bypass_date': False,
        })
        return res

    def _post(self, soft=True):
        if self.env.context.get('skip_overdue_control'):
            return super()._post(soft=soft)

        draft_invoices = self.filtered(
            lambda m: m.move_type == 'out_invoice' and m.state == 'draft' and m.partner_id
        )
        to_log = []
        if draft_invoices:
            can_bypass = self.env.user.has_group('account_overdue_control.group_overdue_control_bypass')
            pairs = [
                (m.partner_id.commercial_partner_id, m.company_id)
                for m in draft_invoices
            ]
            statuses = self.env['res.partner']._get_overdue_control_status_batch(
                pairs,
                exclude_move_ids=draft_invoices.ids,
            )
            blocked = []
            missing_reason = []
            for move in draft_invoices:
                key = (move.partner_id.commercial_partner_id.id, move.company_id.id)
                status = statuses.get(key)
                if not status or not status['blocked']:
                    continue
                if can_bypass:
                    if (move.overdue_bypass_reason or '').strip():
                        to_log.append((move, status))
                    else:
                        missing_reason.append((move, status))
                else:
                    blocked.append((move, status))

            if blocked:
                lines = "\n".join(
                    "- %s: %s" % (
                        move.name if move.name and move.name != '/' else move.partner_id.display_name,
                        status['message'],
                    )
                    for move, status in blocked
                )
                raise UserError(_(
                    "The following invoices cannot be posted because the customer has overdue invoices "
                    "past their payment term due dates:\n%(lines)s\n\n"
                    "Register the pending payments, exempt the customer with a reason, "
                    "or ask an authorized user to bypass the block with a reason.",
                    lines=lines,
                ))

            if missing_reason:
                lines = "\n".join(
                    "- %s: %s" % (
                        move.name if move.name and move.name != '/' else move.partner_id.display_name,
                        status['message'],
                    )
                    for move, status in missing_reason
                )
                raise UserError(_(
                    "A bypass reason is required to post the following invoices for customers with "
                    "overdue invoices:\n%(lines)s\n\n"
                    "Use the 'Bypass block' button on the invoice to enter the authorization reason.",
                    lines=lines,
                ))

            now = fields.Datetime.now()
            for move, _status in to_log:
                vals = {}
                if not move.overdue_bypass_user_id:
                    vals['overdue_bypass_user_id'] = self.env.user.id
                if not move.overdue_bypass_date:
                    vals['overdue_bypass_date'] = now
                if vals:
                    move.write(vals)

        posted = super()._post(soft=soft)

        for move, status in to_log:
            if move.state != 'posted':
                continue
            body = _(
                "Posted by %(user)s bypassing the overdue invoices block. %(message)s Reason: %(reason)s",
                user=self.env.user.display_name,
                message=status['message'],
                reason=(move.overdue_bypass_reason or '').strip(),
            )
            move.message_post(body=Markup("<p>%s</p>") % body)
        return posted
