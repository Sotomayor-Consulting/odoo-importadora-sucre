from datetime import date

from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestReferralSettlement(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.commission_product = cls.env['product.product'].create({
            'name': 'Comision de referidos', 'type': 'service'})
        cls.plan = cls.env['referral.commission.plan'].create({
            'name': 'Plan liq', 'commission_product_id': cls.commission_product.id})
        cls.partner = cls.env['res.partner'].create({
            'name': 'Partner liq', 'is_referral_partner': True,
            'referral_commission_plan_id': cls.plan.id})
        cls.customer = cls.env['res.partner'].create({'name': 'Cliente liq'})

    def _commission(self, amount, on_date):
        return self.env['referral.commission'].create({
            'partner_id': self.partner.id,
            'customer_id': self.customer.id,
            'company_id': self.env.company.id,
            'currency_id': self.env.company.currency_id.id,
            'date': on_date,
            'commission_amount': amount,
            'rate': 15.0,
            'state': 'draft',
        })

    def test_generate_collects_period_commissions(self):
        self._commission(100.0, date(2026, 6, 5))
        self._commission(50.0, date(2026, 6, 20))
        self._commission(80.0, date(2026, 7, 2))  # fuera del periodo
        settlement = self.env['referral.commission.settlement'].create({
            'partner_id': self.partner.id,
            'date_from': date(2026, 6, 1), 'date_to': date(2026, 6, 30)})
        settlement.action_generate()
        self.assertEqual(len(settlement.line_ids), 2, "Solo las de junio")
        self.assertEqual(settlement.amount_total, 150.0)
        self.assertTrue(all(c.state == 'settled' for c in settlement.line_ids))

    def test_payment_due_date_is_15th_next_month(self):
        settlement = self.env['referral.commission.settlement'].create({
            'partner_id': self.partner.id,
            'date_from': date(2026, 6, 1), 'date_to': date(2026, 6, 30)})
        self.assertEqual(settlement.payment_due_date, date(2026, 7, 15))

    def test_create_vendor_bill(self):
        self._commission(150.0, date(2026, 6, 10))
        settlement = self.env['referral.commission.settlement'].create({
            'partner_id': self.partner.id,
            'date_from': date(2026, 6, 1), 'date_to': date(2026, 6, 30)})
        settlement.action_generate()
        settlement.action_create_vendor_bill()
        bill = settlement.vendor_bill_id
        self.assertTrue(bill)
        self.assertEqual(bill.move_type, 'in_invoice')
        self.assertEqual(bill.partner_id, self.partner)
        self.assertEqual(bill.invoice_date_due, date(2026, 7, 15))
        self.assertEqual(settlement.state, 'billed')
