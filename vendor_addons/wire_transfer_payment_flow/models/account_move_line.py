from odoo import models


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    def reconcile(self):
        result = super().reconcile()
        invoices = self._all_reconciled_lines().mapped('move_id').filtered(
            lambda m: m.move_type == 'out_invoice' and m.state == 'posted'
        )
        for invoice in invoices:
            invoice._wpf_release_projects_if_ready()
        return result
