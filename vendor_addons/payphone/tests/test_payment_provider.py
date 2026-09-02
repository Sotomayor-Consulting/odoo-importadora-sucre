# Part of Odoo. See LICENSE file for full copyright and licensing details.

from unittest.mock import patch

from odoo.addons.payphone import const
from odoo.addons.payphone.tests.common import PayphoneCommon
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestPayphoneProvider(PayphoneCommon):
    """Tests for the Payphone payment provider configuration and currency filtering."""

    # ========================
    # Category 1: Provider exists and is configured
    # ========================

    def test_provider_record_exists(self):
        """Verify that the Payphone provider record was created by the XML data."""
        provider = self.env.ref("payphone.payment_provider_payphone")
        self.assertTrue(provider.exists(), "The Payphone provider record must exist.")

    def test_provider_code_is_payphone(self):
        """Verify the provider code is 'payphone'."""
        self.assertEqual(self.provider.code, "payphone")

    def test_provider_has_credentials_fields(self):
        """Verify that API Token and Store ID fields are present and set."""
        # The fields should exist on the model
        self.assertIn("payphone_api_token", self.provider._fields)
        self.assertIn("payphone_store_id", self.provider._fields)
        # The test values we set in setUpClass should persist
        self.assertEqual(self.provider.payphone_api_token, "test-token-abc123")
        self.assertEqual(self.provider.payphone_store_id, "test-store-xyz789")

    def test_provider_default_payment_method_codes(self):
        """Verify the default payment method codes include only 'card'."""
        codes = self.provider._get_default_payment_method_codes()
        self.assertEqual(codes, {"card"})

    def test_provider_api_url(self):
        """Verify the API base URL is correct."""
        self.assertEqual(
            self.provider._payphone_get_api_url(),
            const.API_URL,
        )

    def test_provider_headers_contain_bearer_token(self):
        """Verify that request headers include the Bearer token."""
        headers = self.provider._payphone_get_headers()
        self.assertEqual(headers["Authorization"], "Bearer test-token-abc123")
        self.assertEqual(headers["Content-Type"], "application/json")

    # ========================
    # Category 2: Payphone is only valid for Ecuador (USD)
    # ========================

    def test_supported_currencies_only_usd(self):
        """Verify _get_supported_currencies returns only USD for Payphone."""
        currencies = self.provider._get_supported_currencies()
        currency_names = set(currencies.mapped("name"))
        self.assertEqual(currency_names, {"USD"})

    def test_supported_currencies_excludes_eur(self):
        """Verify EUR is not in the supported currencies."""
        currencies = self.provider._get_supported_currencies()
        currency_names = currencies.mapped("name")
        self.assertNotIn("EUR", currency_names)

    def test_compatible_providers_excludes_payphone_for_eur(self):
        """Verify Payphone is filtered out when currency is EUR.

        _get_compatible_providers requires several positional arguments in Odoo 19:
          company_id, partner_id, amount, currency_id (keyword), ...
        We call it with the minimum required args.
        """
        providers = self.env["payment.provider"]._get_compatible_providers(
            self.provider.company_id.id,
            self.partner.id,
            10.0,
            currency_id=self.currency_eur.id,
        )
        payphone_providers = providers.filtered(lambda p: p.code == "payphone")
        self.assertFalse(
            payphone_providers,
            "Payphone must not appear as compatible when currency is EUR.",
        )

    def test_compatible_providers_includes_payphone_for_usd(self):
        """Verify Payphone is included when currency is USD."""
        providers = self.env["payment.provider"]._get_compatible_providers(
            self.provider.company_id.id,
            self.partner.id,
            10.0,
            currency_id=self.currency_usd.id,
        )
        payphone_providers = providers.filtered(lambda p: p.code == "payphone")
        self.assertTrue(
            payphone_providers,
            "Payphone must appear as compatible when currency is USD.",
        )

    def test_api_request_failure_raises_value_error(self):
        """Verify that a network failure in _payphone_make_request raises ValueError.

        The code catches `requests.exceptions.RequestException`, so the mock must
        raise a subclass of it (e.g., ConnectionError) for the except block to
        trigger and re-raise as ValueError.
        """
        import requests as req

        with patch("requests.post") as mock_post:
            mock_post.side_effect = req.exceptions.ConnectionError("Connection refused")
            with self.assertRaises(ValueError):
                self.provider._payphone_make_request("/button/Prepare", payload={})
