from odoo.fields import Command
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestReferralEngine(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.category = cls.env['product.category'].create({'name': 'Servicios SCI'})
        cls.plan = cls.env['referral.commission.plan'].create({'name': 'Plan motor'})
        cls.env['referral.commission.rule'].create({
            'plan_id': cls.plan.id, 'category_id': cls.category.id, 'rate': 10.0})
        cls.partner = cls.env['res.partner'].create({
            'name': 'Partner motor', 'is_referral_partner': True,
            'referral_commission_plan_id': cls.plan.id})
        cls.customer = cls.env['res.partner'].create({
            'name': 'Cliente referido', 'referrer_partner_id': cls.partner.id})
        cls.product = cls.env['product.product'].create({
            'name': 'Servicio comisionable', 'type': 'service',
            'categ_id': cls.category.id})
        cls.product_fee = cls.env['product.product'].create({
            'name': 'Tasa gubernamental', 'type': 'service',
            'categ_id': cls.category.id, 'referral_commissionable': False})

    def _make_invoice(self):
        return self.env['account.move'].create({
            'move_type': 'out_invoice',
            'partner_id': self.customer.id,
            'invoice_date': '2026-06-01',
            'invoice_line_ids': [
                Command.create({
                    'display_type': 'product',
                    'product_id': self.product.id, 'quantity': 1,
                    'price_unit': 1000.0, 'tax_ids': [Command.clear()]}),
                Command.create({
                    'display_type': 'product',
                    'product_id': self.product_fee.id, 'quantity': 1,
                    'price_unit': 500.0, 'tax_ids': [Command.clear()]}),
            ],
        })

    def test_referrer_inherited_on_invoice(self):
        invoice = self._make_invoice()
        self.assertEqual(invoice.referral_referrer_id, self.partner)

    def test_commission_generated_only_for_commissionable(self):
        invoice = self._make_invoice()
        invoice.action_post()
        invoice._referral_make_commission()
        comms = self.env['referral.commission'].search([('invoice_id', '=', invoice.id)])
        self.assertEqual(len(comms), 1, "Solo la linea comisionable genera comision")
        self.assertEqual(comms.product_id, self.product)
        self.assertEqual(comms.commission_amount, 100.0, "10% de 1000")
        self.assertEqual(comms.partner_id, self.partner)
        self.assertTrue(invoice.referral_commission_generated)

    def test_no_double_generation(self):
        invoice = self._make_invoice()
        invoice.action_post()
        invoice._referral_make_commission()
        invoice._referral_make_commission()
        comms = self.env['referral.commission'].search([('invoice_id', '=', invoice.id)])
        self.assertEqual(len(comms), 1)

    def test_refund_is_clawback(self):
        invoice = self._make_invoice()
        invoice.action_post()
        invoice._referral_make_commission()
        refund = invoice._reverse_moves([{'invoice_date': '2026-06-10'}])
        refund.action_post()
        refund._referral_make_commission()
        clawback = self.env['referral.commission'].search([('invoice_id', '=', refund.id)])
        self.assertEqual(len(clawback), 1)
        self.assertTrue(clawback.is_clawback)
        self.assertEqual(clawback.commission_amount, -100.0)
