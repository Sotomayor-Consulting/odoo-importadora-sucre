from odoo import _, models


class PaymentTransaction(models.Model):
    _inherit = 'payment.transaction'

    def _wpf_is_wire_transfer(self):
        self.ensure_one()
        method_code = (self.payment_method_id.code or '').strip().lower()
        return method_code == 'wire_transfer'

    def _wpf_fix_customer_partner(self):
        for tx in self:
            expected_partner = self.env['res.partner']
            if hasattr(tx, 'invoice_ids') and tx.invoice_ids:
                expected_partner = tx.invoice_ids[:1].partner_id.commercial_partner_id
            elif hasattr(tx, 'sale_order_ids') and tx.sale_order_ids:
                sale_order = tx.sale_order_ids[:1]
                expected_partner = (sale_order.partner_invoice_id or sale_order.partner_id).commercial_partner_id
            if expected_partner and tx.partner_id.commercial_partner_id != expected_partner:
                tx.sudo().write({'partner_id': expected_partner.id})

    def _apply_updates(self, payment_data):
        deferred_txs = self.filtered(lambda tx: tx._wpf_is_wire_transfer())
        other_txs = self - deferred_txs
        if other_txs:
            super(PaymentTransaction, other_txs)._apply_updates(payment_data)
        for tx in deferred_txs:
            tx._wpf_fix_customer_partner()
            tx._set_pending(state_message=_(
                "Transfer reported by customer. Waiting for accounting validation against bank reconciliation."
            ))
