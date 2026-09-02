# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging

from odoo import _, api, fields, models

from odoo.addons.payphone import const

_logger = logging.getLogger(__name__)


class PaymentProvider(models.Model):
    _inherit = 'payment.provider'

    code = fields.Selection(
        selection_add=[('payphone', "Payphone")],
        ondelete={'payphone': 'set default'},
    )
    payphone_api_token = fields.Char(
        string="Payphone API Token",
        required_if_provider='payphone',
        groups='base.group_system',
    )
    payphone_store_id = fields.Char(
        string="Payphone Store ID",
        required_if_provider='payphone',
        groups='base.group_system',
    )
    payphone_fee_percentage = fields.Float(string="Payphone Fee (%)")
    payphone_fee_fixed = fields.Float(string="Payphone Fixed Fee")
    payphone_fee_product_id = fields.Many2one(
        comodel_name='product.product',
        string='Producto del Fee de Payphone',
        domain="[('sale_ok', '=', True)]",
        help='Producto cuya cuenta contable (ingreso/gasto, configurada en el propio '
             'producto) recibe el valor del fee. Su nombre se usa en la linea de la orden.',
    )
    payphone_fee_effective_rate = fields.Float(
        string="Payphone Effective Fee Rate",
        compute='_compute_payphone_fee_effective_rate',
        help="Tasa efectiva del fee (incluye IVA) para mostrar el valor adicional "
             "en el portal de pago. fee% × (1 + IVA).",
    )

    @api.depends('payphone_fee_percentage', 'payphone_fee_product_id')
    def _compute_payphone_fee_effective_rate(self):
        default_product = self.env.ref(
            'payphone.product_payphone_fee', raise_if_not_found=False
        )
        for provider in self:
            fee_product = provider.payphone_fee_product_id or default_product
            tax_rate = 0.0
            if fee_product and fee_product.taxes_id:
                tax_rate = sum(fee_product.taxes_id.mapped('amount')) / 100.0
            if provider.code == 'payphone' and provider.payphone_fee_percentage > 0:
                provider.payphone_fee_effective_rate = (
                    provider.payphone_fee_percentage / 100.0
                ) * (1 + tax_rate)
            else:
                provider.payphone_fee_effective_rate = 0.0

    # === Business methods ===#

    @api.model
    def _get_compatible_providers(self, *args, currency_id=None, **kwargs):
        """Override to filter out Payphone if the currency is not USD."""
        providers = super()._get_compatible_providers(
            *args, currency_id=currency_id, **kwargs
        )
        currency = self.env['res.currency'].browse(currency_id).exists()
        if currency and currency.name != 'USD':
            providers = providers.filtered(lambda p: p.code != 'payphone')
        return providers

    def _get_supported_currencies(self):
        """Override to return only USD for Payphone."""
        supported_currencies = super()._get_supported_currencies()
        if self.code == 'payphone':
            supported_currencies = supported_currencies.filtered(
                lambda c: c.name == 'USD'
            )
        return supported_currencies

    def _get_default_payment_method_codes(self):
        """Override to return the default payment method codes for Payphone."""
        self.ensure_one()
        if self.code != 'payphone':
            return super()._get_default_payment_method_codes()
        return const.DEFAULT_PAYMENT_METHOD_CODES

    # === Payphone API helpers ===#

    def _payphone_get_api_url(self):
        """Return the Payphone API base URL."""
        self.ensure_one()
        return const.API_URL

    def _payphone_get_headers(self):
        """Return the headers for Payphone API requests."""
        self.ensure_one()
        return {
            'Authorization': f'Bearer {self.payphone_api_token}',
            'Content-Type': 'application/json',
        }

    def _payphone_make_request(self, endpoint, payload=None):
        """Make a request to the Payphone API and return the response.

        :param str endpoint: The API endpoint to call (e.g., '/button/Prepare').
        :param dict payload: The JSON payload for POST requests.
        :return: The JSON-decoded response content.
        :rtype: dict
        :raises UserError: If the request fails.
        """
        self.ensure_one()
        import requests as req

        api_url = self._payphone_get_api_url()
        headers = self._payphone_get_headers()
        url = f'{api_url}{endpoint}'

        _logger.info(
            "Payphone request to %s:\n%s",
            url,
            payload,
        )

        try:
            response = req.post(url, json=payload, headers=headers, timeout=30)
            response.raise_for_status()
            result = response.json()
        except req.exceptions.HTTPError as e:
            # Capture the response body — Payphone includes error details
            error_detail = ''
            try:
                error_detail = e.response.text
            except Exception:
                pass
            _logger.error(
                "Payphone HTTP error %s from %s: %s\nPayload: %s\nResponse body: %s",
                e.response.status_code, url, e, payload, error_detail,
            )
            raise ValueError(
                _("Payphone returned an error (%(code)s). Details: %(detail)s",
                  code=e.response.status_code,
                  detail=error_detail or str(e))
            ) from e
        except req.exceptions.ConnectionError as e:
            _logger.error("Payphone connection error to %s: %s", url, e)
            raise ValueError(
                _("Could not connect to Payphone. Please try again later.")
            ) from e
        except req.exceptions.Timeout as e:
            _logger.error("Payphone request to %s timed out: %s", url, e)
            raise ValueError(
                _("Payphone request timed out. Please try again later.")
            ) from e
        except req.exceptions.RequestException as e:
            _logger.error("Payphone request to %s failed: %s", url, e)
            raise ValueError(
                _("Could not connect to Payphone. Please try again later.")
            ) from e

        _logger.info("Payphone response from %s:\n%s", url, result)
        return result
