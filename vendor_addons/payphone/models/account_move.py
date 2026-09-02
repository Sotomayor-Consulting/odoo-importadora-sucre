# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models


class AccountMove(models.Model):
    _inherit = 'account.move'

    def _payphone_existing_fee_total(self):
        """Total (con IVA) de las lineas de fee Payphone ya presentes en la factura.

        Se usa en el card del portal: si el fee ya esta en la factura, se muestra ese
        valor en vez de recalcularlo sobre el total (que ya lo incluye)."""
        self.ensure_one()
        if not self.invoice_line_ids:
            return 0.0
        fee_products = self.env['payment.transaction'].sudo()._payphone_fee_products()
        if not fee_products:
            return 0.0
        lines = self.invoice_line_ids.filtered(lambda l: l.product_id.id in fee_products.ids)
        return sum(lines.mapped('price_total'))
