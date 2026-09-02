from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestReferralAssignment(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env['res.partner'].create({
            'name': 'Partner referidor',
            'is_referral_partner': True,
        })

    def test_partner_by_referral_code_case_insensitive(self):
        found = self.env['res.partner']._sci_partner_by_referral_code(
            self.partner.referral_code.lower())
        self.assertEqual(found, self.partner)

    def test_partner_by_referral_code_unknown(self):
        self.assertFalse(
            self.env['res.partner']._sci_partner_by_referral_code('NOEXISTE'))

    def test_code_entry_sets_referrer(self):
        customer = self.env['res.partner'].create({'name': 'Cliente'})
        customer.referral_code_entry = self.partner.referral_code
        customer._onchange_referral_code_entry()
        self.assertEqual(customer.referrer_partner_id, self.partner)

    def test_referred_count_and_cartera(self):
        c1 = self.env['res.partner'].create({
            'name': 'C1', 'referrer_partner_id': self.partner.id})
        c2 = self.env['res.partner'].create({
            'name': 'C2', 'referrer_partner_id': self.partner.id})
        self.assertEqual(self.partner.referred_partner_count, 2)
        self.assertIn(c1, self.partner.referred_partner_ids)
        self.assertIn(c2, self.partner.referred_partner_ids)

    def test_sale_order_inherits_referrer(self):
        customer = self.env['res.partner'].create({
            'name': 'Cliente referido', 'referrer_partner_id': self.partner.id})
        order = self.env['sale.order'].create({'partner_id': customer.id})
        self.assertEqual(order.referrer_id, self.partner)
