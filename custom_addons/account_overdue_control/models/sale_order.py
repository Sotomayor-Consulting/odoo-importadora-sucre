from markupsafe import Markup

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError


class SaleOrder(models.Model):
    _inherit = 'sale.order'

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

    @api.depends('partner_id', 'company_id', 'state')
    def _compute_overdue_control(self):
        candidates = self.filtered(
            lambda o: o.state in ('draft', 'sent') and o.partner_id
        )
        for order in self - candidates:
            order.overdue_control_blocked = False
            order.overdue_control_message = ''
        if not candidates:
            return

        pairs = [
            (o.partner_id._origin.commercial_partner_id, o.company_id._origin)
            for o in candidates
        ]
        statuses = self.env['res.partner']._get_overdue_control_status_batch(pairs)
        for order in candidates:
            key = (order.partner_id._origin.commercial_partner_id.id, order.company_id._origin.id)
            status = statuses.get(key)
            if status and status['blocked']:
                order.overdue_control_blocked = True
                order.overdue_control_message = status['message']
            else:
                order.overdue_control_blocked = False
                order.overdue_control_message = ''

    def _compute_overdue_control_can_view_invoices(self):
        can_view = (
            self.env.user.has_group('account.group_account_readonly')
            or self.env.user.has_group('account.group_account_invoice')
        )
        self.overdue_control_can_view_invoices = can_view

    def _get_overdue_control_status(self):
        self.ensure_one()
        if self.state not in ('draft', 'sent') or not self.partner_id:
            return self.env['res.partner']._empty_overdue_status()
        return self.partner_id._get_overdue_control_status(self.company_id)

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
            raise UserError(_("This sales order is not currently blocked by overdue invoices."))
        return {
            'type': 'ir.actions.act_window',
            'name': _('Bypass Overdue Invoices Block'),
            'res_model': 'account.overdue.bypass.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_res_model': 'sale.order',
                'default_res_id': self.id,
                'default_partner_id': self.partner_id.commercial_partner_id.id,
                'default_overdue_message': status['message'],
            },
        }

    def action_draft(self):
        res = super().action_draft()
        self.filtered('overdue_bypass_reason').write({
            'overdue_bypass_reason': False,
            'overdue_bypass_user_id': False,
            'overdue_bypass_date': False,
        })
        return res

    def action_confirm(self):
        if self.env.context.get('skip_overdue_control'):
            return super().action_confirm()

        quotations = self.filtered(lambda o: o.state in ('draft', 'sent') and o.partner_id)
        to_log = []
        if quotations:
            can_bypass = self.env.user.has_group('account_overdue_control.group_overdue_control_bypass')
            pairs = [
                (o.partner_id.commercial_partner_id, o.company_id)
                for o in quotations
            ]
            statuses = self.env['res.partner']._get_overdue_control_status_batch(pairs)
            blocked = []
            missing_reason = []
            for order in quotations:
                key = (order.partner_id.commercial_partner_id.id, order.company_id.id)
                status = statuses.get(key)
                if not status or not status['blocked']:
                    continue
                if can_bypass:
                    if (order.overdue_bypass_reason or '').strip():
                        to_log.append((order, status))
                    else:
                        missing_reason.append((order, status))
                else:
                    blocked.append((order, status))

            if blocked:
                lines = "\n".join(
                    "- %s: %s" % (order.name or order.partner_id.display_name, status['message'])
                    for order, status in blocked
                )
                raise UserError(_(
                    "The following sales orders cannot be confirmed and must remain as quotations "
                    "because the customer has overdue invoices past their payment term due dates:\n"
                    "%(lines)s\n\n"
                    "Register the pending payments, exempt the customer with a reason, "
                    "or ask an authorized user to bypass the block with a reason.",
                    lines=lines,
                ))

            if missing_reason:
                lines = "\n".join(
                    "- %s: %s" % (order.name or order.partner_id.display_name, status['message'])
                    for order, status in missing_reason
                )
                raise UserError(_(
                    "A bypass reason is required to confirm the following sales orders for customers "
                    "with overdue invoices:\n%(lines)s\n\n"
                    "Use the 'Bypass block' button on the quotation to enter the authorization reason.",
                    lines=lines,
                ))

            now = fields.Datetime.now()
            for order, _status in to_log:
                vals = {}
                if not order.overdue_bypass_user_id:
                    vals['overdue_bypass_user_id'] = self.env.user.id
                if not order.overdue_bypass_date:
                    vals['overdue_bypass_date'] = now
                if vals:
                    order.write(vals)

        res = super().action_confirm()

        for order, status in to_log:
            if order.state != 'sale':
                continue
            body = _(
                "Order confirmed by %(user)s bypassing the overdue invoices block. %(message)s Reason: %(reason)s",
                user=self.env.user.display_name,
                message=status['message'],
                reason=(order.overdue_bypass_reason or '').strip(),
            )
            order.message_post(body=Markup("<p>%s</p>") % body)
        return res
