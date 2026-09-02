from odoo import _, api, fields, models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    wpf_project_creation_policy = fields.Selection(
        string='Project Creation Policy',
        selection=[
            ('partner_default', 'Use Customer Default'),
            ('on_confirm', 'On Sales Order Confirmation'),
            ('on_first_payment', 'On First Payment'),
            ('on_paid', 'When Invoice Is Fully Paid'),
        ],
        default='partner_default',
        required=True,
    )
    wpf_project_creation_policy_effective = fields.Selection(
        string='Effective Project Policy',
        selection=[
            ('on_confirm', 'On Sales Order Confirmation'),
            ('on_first_payment', 'On First Payment'),
            ('on_paid', 'When Invoice Is Fully Paid'),
        ],
        compute='_compute_wpf_project_creation_policy_effective',
        store=True,
    )
    wpf_project_created_by_flow = fields.Boolean(
        string='Project Created By Payment Flow',
        default=False,
        copy=False,
        readonly=True,
    )

    @api.depends('wpf_project_creation_policy', 'partner_id.wpf_project_creation_policy')
    def _compute_wpf_project_creation_policy_effective(self):
        for order in self:
            if order.wpf_project_creation_policy == 'partner_default':
                order.wpf_project_creation_policy_effective = order.partner_id.wpf_project_creation_policy
            else:
                order.wpf_project_creation_policy_effective = order.wpf_project_creation_policy

    def _wpf_can_create_project(self):
        self.ensure_one()
        if self.state not in ('sale', 'done') or self.project_ids or self.wpf_project_created_by_flow:
            return False
        if self.wpf_project_creation_policy_effective == 'on_confirm':
            return True
        invoices = self.invoice_ids.filtered(lambda inv: inv.move_type == 'out_invoice' and inv.state == 'posted')
        if not invoices:
            return False
        if self.wpf_project_creation_policy_effective == 'on_paid':
            return any(inv.payment_state == 'paid' for inv in invoices)
        return any(inv.currency_id.compare_amounts(inv.amount_residual, inv.amount_total) < 0 for inv in invoices)

    def action_confirm(self):
        blocked_orders = self.filtered(
            lambda o: o.wpf_project_creation_policy_effective in ('on_first_payment', 'on_paid')
        )
        allowed_orders = self - blocked_orders

        result = True
        if allowed_orders:
            result = super(SaleOrder, allowed_orders).action_confirm()
        if blocked_orders:
            result = super(SaleOrder, blocked_orders.with_context(disable_project_task_generation=True)).action_confirm()
        return result

    def action_wpf_create_project(self):
        for order in self:
            if not order._wpf_can_create_project():
                continue
            order.order_line.sudo().with_company(order.company_id)._timesheet_service_generation()
            order.wpf_project_created_by_flow = True
            order.message_post(body=_("Project and tasks created by payment flow policy."))
        return True
