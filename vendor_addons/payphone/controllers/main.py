# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging
from pprint import pformat

from odoo import http
from odoo.http import request

from odoo.addons.payphone import const

_logger = logging.getLogger(__name__)


class PayphoneController(http.Controller):

    @http.route(
        const.RETURN_URL,
        type='http',
        auth='public',
        methods=['GET'],
        csrf=False,
        save_session=False,
    )
    def payphone_return(self, **data):
        """Handle the return from Payphone after payment.

        Payphone redirects back with `id` and `clientTransactionId` as query
        parameters. We verify the transaction by calling the Confirm API, then
        delegate to `_process()` which calls `_apply_updates()`.
        """
        _logger.info(
            "Handling redirection from Payphone with data:\n%s", pformat(data)
        )

        payphone_id = data.get('id')
        client_tx_id = data.get('clientTransactionId')

        if not payphone_id or not client_tx_id:
            _logger.warning("Payphone return missing required parameters.")
            return request.redirect('/payment/status')

        # Find the transaction
        tx_sudo = request.env['payment.transaction'].sudo()._search_by_reference(
            'payphone', {'clientTransactionId': client_tx_id}
        )
        if not tx_sudo:
            _logger.warning(
                "No transaction found for Payphone clientTransactionId=%s",
                client_tx_id,
            )
            return request.redirect('/payment/status')

        # Verify the transaction with Payphone's Confirm API
        # This is critical: never trust redirect params directly.
        try:
            verified_data = tx_sudo.provider_id._payphone_make_request(
                '/button/V2/Confirm',
                payload={
                    'id': int(payphone_id),
                    'clientTxId': client_tx_id,
                },
            )
        except Exception:
            _logger.exception(
                "Payphone Confirm request failed for tx %s", client_tx_id
            )
            return request.redirect('/payment/status')

        # Add the original payphone_id in case transactionId is missing
        verified_data['payphone_id'] = payphone_id

        # Process the transaction using the Odoo 19 pattern
        tx_sudo._process('payphone', verified_data)

        return request.redirect('/payment/status')

    @http.route(
        const.CANCEL_URL,
        type='http',
        auth='public',
        methods=['GET'],
        csrf=False,
        save_session=False,
    )
    def payphone_cancel(self, **data):
        """Handle the cancellation from Payphone.

        When the user clicks the X button on the Payphone payment form, they
        are redirected to this URL.
        """
        _logger.info(
            "Handling cancellation from Payphone with data:\n%s", pformat(data)
        )

        client_tx_id = data.get('clientTransactionId')
        if not client_tx_id:
            return request.redirect('/payment/status')

        tx_sudo = request.env['payment.transaction'].sudo()._search_by_reference(
            'payphone', {'clientTransactionId': client_tx_id}
        )
        if tx_sudo:
            tx_sudo._payphone_remove_fee_section(tx_sudo.sale_order_ids)
            tx_sudo._set_canceled(
                state_message="Payment cancelled by the user on Payphone."
            )

        return request.redirect('/payment/status')
