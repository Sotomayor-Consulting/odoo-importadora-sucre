from unittest.mock import patch

from odoo.addons.payphone import const
from odoo.addons.payphone.tests.common import PayphoneCommon
from odoo.exceptions import ValidationError
from odoo.tests import tagged


@tagged("post_install", "-at_install")
class TestPayphoneTransaction(PayphoneCommon):
    """Tests for Payphone payment transaction processing."""

    # ========================
    # Category 3: Valid transaction creation
    # ========================
    def test_create_transaction_with_valid_data(self):
        """Verify a transaction can be created with valid Payphone data."""
        tx = self.env["payment.transaction"].create(
            {
                "provider_id": self.provider.id,
                "payment_method_id": self.payment_method_card.id,
                "reference": "TEST-PAYPHONE-VALID-001",
                "amount": 25.50,
                "currency_id": self.currency_usd.id,
                "partner_id": self.partner.id,
            }
        )
        self.assertTrue(tx.exists())
        self.assertEqual(tx.provider_code, "payphone")
        self.assertEqual(tx.amount, 25.50)
        self.assertEqual(tx.currency_id, self.currency_usd)

    def test_transaction_reference_is_set(self):
        """Verify the transaction reference is properly assigned on creation."""
        tx = self.env["payment.transaction"].create(
            {
                "provider_id": self.provider.id,
                "payment_method_id": self.payment_method_card.id,
                "reference": "TEST-REF-UNIQUE-42",
                "amount": 5.00,
                "currency_id": self.currency_usd.id,
                "partner_id": self.partner.id,
            }
        )
        self.assertEqual(tx.reference, "TEST-REF-UNIQUE-42")

    def test_extract_reference_valid_data(self):
        """Verify _extract_reference returns the clientTransactionId from payment data."""
        reference = self.env["payment.transaction"]._extract_reference(
            "payphone", {"clientTransactionId": "REF-PAYPHONE-001"}
        )
        self.assertEqual(reference, "REF-PAYPHONE-001")

    def test_extract_amount_data_converts_cents_to_major(self):
        """Verify _extract_amount_data converts cents to major currency units.
        Payphone sends amounts in cents (e.g., 1050 = $10.50).
        The method should convert to major units using the currency's decimal places.
        """
        result = self.transaction._extract_amount_data(
            {
                "amount": 1050,
                "currency": "USD",
            }
        )
        self.assertIsNotNone(result)
        self.assertEqual(result["amount"], 10.50)
        self.assertEqual(result["currency_code"], "USD")

    def test_extract_amount_data_returns_none_when_no_amount(self):
        """Verify _extract_amount_data returns None when amount is missing.
        When the amount is not present in the payment data, the method should
        return None to skip amount validation.
        """
        result = self.transaction._extract_amount_data({})
        self.assertIsNone(result)

    def test_extract_amount_data_defaults_currency_to_usd(self):
        """Verify _extract_amount_data defaults to USD when currency is missing."""
        result = self.transaction._extract_amount_data({"amount": 500})
        self.assertIsNotNone(result)
        self.assertEqual(result["currency_code"], "USD")

    def test_rendering_values_with_valid_api_response(self):
        """Verify _get_specific_rendering_values returns the redirect URL.
        We mock _payphone_make_request to return a valid response with payWithCard URL.
        """
        mock_response = {
            "payWithCard": "https://pay.payphone.com/checkout/abc123",
            "payWithPayphone": "https://pay.payphone.com/pp/abc123",
        }
        with patch.object(
            type(self.provider),
            "_payphone_make_request",
            return_value=mock_response,
        ):
            result = self.transaction._get_specific_rendering_values({})
            self.assertEqual(
                result["api_url"],
                "https://pay.payphone.com/checkout/abc123",
            )

    # ========================
    # Category 4: Invalid data triggers expected errors
    # ========================
    def test_extract_reference_missing_client_tx_id(self):
        """Verify _extract_reference raises ValidationError when clientTransactionId is missing."""
        with self.assertRaises(ValidationError):
            self.env["payment.transaction"]._extract_reference("payphone", {})

    def test_extract_reference_empty_client_tx_id(self):
        """Verify _extract_reference raises ValidationError when clientTransactionId is empty."""
        with self.assertRaises(ValidationError):
            self.env["payment.transaction"]._extract_reference(
                "payphone", {"clientTransactionId": ""}
            )

    def test_rendering_values_raises_on_missing_pay_url(self):
        """Verify _get_specific_rendering_values raises when API returns no payWithCard URL.
        When Payphone returns an error (no payWithCard key), the method should
        raise a ValidationError with the error message from the API.
        """
        mock_response = {"message": "Invalid store configuration"}
        with patch.object(
            type(self.provider),
            "_payphone_make_request",
            return_value=mock_response,
        ):
            with self.assertRaises(ValidationError):
                self.transaction._get_specific_rendering_values({})

    # ========================
    # Category 5: State transitions (pending, done, cancel, error)
    # ========================
    def _create_draft_transaction(self, reference):
        """Helper: create a fresh transaction in draft state."""
        return self.env["payment.transaction"].create(
            {
                "provider_id": self.provider.id,
                "payment_method_id": self.payment_method_card.id,
                "reference": reference,
                "amount": 15.00,
                "currency_id": self.currency_usd.id,
                "partner_id": self.partner.id,
            }
        )

    def test_apply_updates_status_done(self):
        """Verify statusCode=3 transitions the transaction to 'done'."""
        tx = self._create_draft_transaction("TEST-DONE-001")
        tx._apply_updates(
            {
                "statusCode": 3,
                "transactionId": "99001",
                "transactionStatus": "Approved",
                "authorizationCode": "AUTH123",
            }
        )
        self.assertEqual(tx.state, "done")

    def test_apply_updates_status_canceled(self):
        """Verify statusCode=2 transitions the transaction to 'cancel'."""
        tx = self._create_draft_transaction("TEST-CANCEL-001")
        tx._apply_updates(
            {
                "statusCode": 2,
                "transactionId": "99002",
                "transactionStatus": "Rejected",
            }
        )
        self.assertEqual(tx.state, "cancel")

    def test_apply_updates_status_pending(self):
        """Verify statusCode=1 (unmapped) transitions the transaction to 'pending'."""
        tx = self._create_draft_transaction("TEST-PENDING-001")
        tx._apply_updates(
            {
                "statusCode": 1,
                "transactionId": "99003",
                "transactionStatus": "Processing",
            }
        )
        self.assertEqual(tx.state, "pending")

    def test_apply_updates_unknown_status_goes_pending(self):
        """Verify an unrecognized statusCode (e.g., 99) defaults to 'pending'."""
        tx = self._create_draft_transaction("TEST-UNKNOWN-001")
        tx._apply_updates(
            {
                "statusCode": 99,
                "transactionId": "99004",
                "transactionStatus": "Unknown",
            }
        )
        self.assertEqual(tx.state, "pending")

    def test_cancel_state_message_contains_status(self):
        """Verify the state_message on cancel includes the Payphone status."""
        tx = self._create_draft_transaction("TEST-CANCEL-MSG-001")
        tx._apply_updates(
            {
                "statusCode": 2,
                "transactionId": "99005",
                "transactionStatus": "Card Declined",
            }
        )
        self.assertEqual(tx.state, "cancel")
        self.assertIn("Card Declined", tx.state_message)

    def test_pending_state_message_contains_status(self):
        """Verify the state_message on pending includes the Payphone status."""
        tx = self._create_draft_transaction("TEST-PENDING-MSG-001")
        tx._apply_updates(
            {
                "statusCode": 1,
                "transactionId": "99006",
                "transactionStatus": "Awaiting confirmation",
            }
        )
        self.assertEqual(tx.state, "pending")
        self.assertIn("Awaiting confirmation", tx.state_message)

    # ========================
    # Category 6: References/external identifiers stored correctly
    # ========================
    def test_provider_reference_from_transaction_id(self):
        """Verify provider_reference stores transactionId when present."""
        tx = self._create_draft_transaction("TEST-TXID-001")
        tx._apply_updates(
            {
                "statusCode": 3,
                "transactionId": "12345",
                "transactionStatus": "Approved",
            }
        )
        self.assertEqual(tx.provider_reference, "12345")

    def test_provider_reference_from_payphone_id_fallback(self):
        """Verify provider_reference falls back to payphone_id when transactionId is absent."""
        tx = self._create_draft_transaction("TEST-PPID-001")
        tx._apply_updates(
            {
                "statusCode": 3,
                "payphone_id": "67890",
                "transactionStatus": "Approved",
            }
        )
        self.assertEqual(tx.provider_reference, "67890")

    def test_provider_reference_from_id_field(self):
        """Verify provider_reference falls back to 'id' when transactionId/payphone_id are absent."""
        tx = self._create_draft_transaction("TEST-ID-001")
        tx._apply_updates(
            {
                "statusCode": 3,
                "id": "11111",
                "transactionStatus": "Approved",
            }
        )
        self.assertEqual(tx.provider_reference, "11111")

    def test_provider_reference_empty_when_no_ids(self):
        """Verify provider_reference is empty string when no ID fields are present."""
        tx = self._create_draft_transaction("TEST-NOID-001")
        tx._apply_updates(
            {
                "statusCode": 3,
                "transactionStatus": "Approved",
            }
        )
        self.assertEqual(tx.provider_reference, "")

    def test_xmlid_provider_payphone_resolves(self):
        """Verify the external ID payphone.payment_provider_payphone resolves correctly."""
        provider = self.env.ref("payphone.payment_provider_payphone")
        self.assertTrue(provider.exists())
        self.assertEqual(provider.code, "payphone")

    def test_provider_reference_prefers_transaction_id_over_payphone_id(self):
        """Verify transactionId takes priority over payphone_id in provider_reference."""
        tx = self._create_draft_transaction("TEST-PRIORITY-001")
        tx._apply_updates(
            {
                "statusCode": 3,
                "transactionId": "TX-PRIMARY",
                "payphone_id": "PP-SECONDARY",
                "id": "ID-TERTIARY",
                "transactionStatus": "Approved",
            }
        )
        self.assertEqual(tx.provider_reference, "TX-PRIMARY")
