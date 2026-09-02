from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged
from odoo.tools import mute_logger


@tagged('post_install', '-at_install')
class TestReferralRates(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.cat_root = cls.env['product.category'].create({'name': 'Servicios SCI'})
        cls.cat_incorp = cls.env['product.category'].create({
            'name': 'Incorporacion', 'parent_id': cls.cat_root.id})
        cls.cat_account = cls.env['product.category'].create({
            'name': 'Contabilidad', 'parent_id': cls.cat_root.id})
        cls.prod_incorp = cls.env['product.product'].create({
            'name': 'LLC EE.UU.', 'type': 'service', 'categ_id': cls.cat_incorp.id})
        cls.prod_account = cls.env['product.product'].create({
            'name': 'Cierre contable', 'type': 'service', 'categ_id': cls.cat_account.id})
        cls.plan = cls.env['referral.commission.plan'].create({'name': 'Plan test'})
        cls.env['referral.commission.rule'].create([
            {'plan_id': cls.plan.id, 'category_id': cls.cat_root.id,
             'rate': 5.0, 'sequence': 100},
            {'plan_id': cls.plan.id, 'category_id': cls.cat_incorp.id,
             'rate': 15.0, 'sequence': 10},
        ])

    def test_rate_deeper_category_wins(self):
        self.assertEqual(self.plan._match_rules(self.prod_incorp).rate, 15.0,
                         "Incorporacion (categoria mas profunda) gana sobre el catch-all")
        self.assertEqual(self.plan._match_rules(self.prod_account).rate, 5.0,
                         "Sin regla propia, aplica el catch-all 5%")

    def test_product_rule_wins(self):
        self.env['referral.commission.rule'].create({
            'plan_id': self.plan.id, 'product_id': self.prod_account.id,
            'rate': 8.0, 'sequence': 50})
        self.assertEqual(self.plan._match_rules(self.prod_account).rate, 8.0,
                         "Una regla por servicio prevalece sobre la categoria")

    def test_no_rule_returns_empty(self):
        empty_plan = self.env['referral.commission.plan'].create({'name': 'Vacio'})
        self.assertFalse(empty_plan._match_rules(self.prod_incorp))

    def test_compute_commission_percentage_and_cap(self):
        rule = self.plan._match_rules(self.prod_incorp)  # 15%
        self.assertEqual(rule._compute_commission(1000.0), 150.0)
        rule.max_commission = 100.0
        self.assertEqual(rule._compute_commission(1000.0), 100.0, "Aplica el tope")

    def test_compute_commission_fixed_amount(self):
        fixed_plan = self.env['referral.commission.plan'].create({'name': 'Fijo'})
        rule = self.env['referral.commission.rule'].create({
            'plan_id': fixed_plan.id, 'product_id': self.prod_account.id,
            'commission_type': 'fixed', 'fixed_amount': 50.0})
        matched = fixed_plan._match_rules(self.prod_account)
        self.assertEqual(matched, rule, "Una regla solo por servicio (sin categoria) aplica")
        self.assertEqual(matched._compute_commission(9999.0), 50.0)

    def test_rule_requires_category_or_product(self):
        with self.assertRaises(ValidationError), mute_logger('odoo.sql_db'):
            self.env['referral.commission.rule'].create({
                'plan_id': self.plan.id, 'rate': 5.0})

    def test_commissionable_default_true(self):
        self.assertTrue(self.prod_incorp.referral_commissionable)

    def test_program_plan_seeded_and_assigned(self):
        plan = self.env.ref('sci_referral_partner.plan_program')
        self.assertTrue(plan)
        partner = self.env['res.partner'].create({
            'name': 'Partner con plan', 'is_referral_partner': True})
        self.assertEqual(partner.referral_commission_plan_id, plan)
