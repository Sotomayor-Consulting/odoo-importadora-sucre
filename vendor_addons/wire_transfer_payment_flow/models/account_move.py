from odoo import api, models


class AccountMove(models.Model):
    _inherit = 'account.move'

    @api.model
    def _cron_wpf_release_projects(self):
        # Backward-compatible no-op for legacy scheduled action records.
        return True

    def _wpf_release_projects_if_ready(self):
        sale_orders = self.invoice_line_ids.mapped('sale_line_ids.order_id').filtered(
            lambda so: so.state in ('sale', 'done') and not so.project_ids
        )
        for order in sale_orders:
            if order._wpf_can_create_project():
                order.action_wpf_create_project()

    def write(self, vals):
        result = super().write(vals)
        trigger_fields = {'payment_state', 'amount_residual'}
        if trigger_fields.intersection(vals):
            for move in self.filtered(lambda m: m.move_type == 'out_invoice' and m.state == 'posted'):
                move._wpf_release_projects_if_ready()
        return result
