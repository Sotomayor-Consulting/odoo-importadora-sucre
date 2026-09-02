from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestReferralPartnerCode(TransactionCase):

    def test_code_generated_on_create(self):
        partner = self.env['res.partner'].create({
            'name': 'Partner A',
            'is_referral_partner': True,
        })
        self.assertTrue(partner.referral_code, "Debe generarse un codigo")
        self.assertEqual(len(partner.referral_code), 10)
        self.assertTrue(all(c in '0123456789ABCDEF' for c in partner.referral_code),
                        "El codigo debe ser hex en mayusculas")

    def test_no_code_for_normal_partner(self):
        partner = self.env['res.partner'].create({'name': 'Cliente normal'})
        self.assertFalse(partner.referral_code)

    def test_code_generated_on_write(self):
        partner = self.env['res.partner'].create({'name': 'Partner B'})
        self.assertFalse(partner.referral_code)
        partner.is_referral_partner = True
        self.assertTrue(partner.referral_code)

    def test_code_not_regenerated(self):
        partner = self.env['res.partner'].create({
            'name': 'Partner C',
            'is_referral_partner': True,
        })
        code = partner.referral_code
        partner.write({'name': 'Partner C (editado)'})
        self.assertEqual(partner.referral_code, code, "El codigo no debe regenerarse")

    def test_codes_are_unique(self):
        p1 = self.env['res.partner'].create({'name': 'P1', 'is_referral_partner': True})
        p2 = self.env['res.partner'].create({'name': 'P2', 'is_referral_partner': True})
        self.assertNotEqual(p1.referral_code, p2.referral_code)

    def test_convert_wizard(self):
        contact = self.env['res.partner'].create({'name': 'Futuro partner'})
        wizard = self.env['sci.referral.partner.convert'].with_context(
            active_id=contact.id).create({
                'referral_contract_end_date': '2027-01-01',
            })
        self.assertEqual(wizard.partner_id, contact)
        wizard.action_convert()
        self.assertTrue(contact.is_referral_partner)
        self.assertTrue(contact.referral_code)
        self.assertEqual(str(contact.referral_contract_end_date), '2027-01-01')

    def test_merge_preserves_partner_code(self):
        # Fusionar un partner (con codigo) dentro de un contacto sin codigo no debe
        # romper la constraint unique; el superviviente conserva codigo y rol.
        Wizard = self.env['base.partner.merge.automatic.wizard']
        partner = self.env['res.partner'].create({
            'name': 'Partner X', 'is_referral_partner': True})
        code = partner.referral_code
        contact = self.env['res.partner'].create({'name': 'Contacto duplicado'})
        Wizard._merge([partner.id, contact.id], dst_partner=contact)
        self.assertFalse(partner.exists(), "La fuente se elimina")
        self.assertTrue(contact.is_referral_partner, "El superviviente queda como Partner")
        self.assertEqual(contact.referral_code, code, "Conserva el codigo del Partner")
