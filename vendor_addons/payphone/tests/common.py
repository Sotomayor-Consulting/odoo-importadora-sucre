# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class PayphoneCommon(TransactionCase):
    """Shared setup for all Payphone payment provider tests.

    Provides:
        - cls.provider: the Payphone payment.provider record (in 'test' mode)
        - cls.currency_usd: the USD res.currency record
        - cls.currency_eur: the EUR res.currency record
        - cls.partner: a test res.partner (Ecuador, with phone/email/vat)
        - cls.transaction: a base payment.transaction in USD linked to the provider
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        # --- Provider ---
        cls.provider = cls.env["payment.provider"].search(
            [("code", "=", "payphone")],
            limit=1,
        )
        if not cls.provider:
            cls.provider = cls.env.ref("payphone.payment_provider_payphone")

        # Activate in test mode and set fake credentials
        cls.provider.write(
            {
                "state": "test",
                "payphone_api_token": "test-token-abc123",
                "payphone_store_id": "test-store-xyz789",
            }
        )

        # --- Currencies ---
        cls.currency_usd = cls.env.ref("base.USD")
        cls.currency_eur = cls.env.ref("base.EUR")

        # Make sure both currencies are active for the tests
        cls.currency_usd.active = True
        cls.currency_eur.active = True

        # --- Payment Method ---
        cls.payment_method_card = cls.env.ref("payment.payment_method_card")

        # --- Partner ---
        cls.partner = cls.env["res.partner"].create(
            {
                "name": "Test Partner Ecuador",
                "email": "testpartner@payphone.ec",
                "phone": "+593991234567",
                "country_id": cls.env.ref("base.ec").id,
                "vat": "1712345678001",
            }
        )

        # --- Base Transaction ---
        cls.transaction = cls.env["payment.transaction"].create(
            {
                "provider_id": cls.provider.id,
                "payment_method_id": cls.payment_method_card.id,
                "reference": "TEST-PAYPHONE-001",
                "amount": 10.00,
                "currency_id": cls.currency_usd.id,
                "partner_id": cls.partner.id,
            }
        )
