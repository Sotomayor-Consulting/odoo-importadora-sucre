import { patch } from '@web/core/utils/patch';

import { PaymentForm } from '@payment/interactions/payment_form';

patch(PaymentForm.prototype, {

    /**
     * Override the redirect flow for Payphone to use window.location.href instead
     * of form.submit().
     *
     * Payphone validates the Referer header to ensure the redirect comes from the
     * registered domain. Using form.submit() on a dynamically created form does not
     * reliably send the Referer header in all browsers, causing Payphone to reject
     * the request with "Not authorized". Using window.location.href ensures the
     * browser sends the correct Referer header.
     *
     * @override method from @payment/interactions/payment_form
     * @private
     * @param {string} providerCode - The code of the selected payment option's provider.
     * @param {number} paymentOptionId - The id of the selected payment option.
     * @param {string} paymentMethodCode - The code of the selected payment method, if any.
     * @param {object} processingValues - The processing values of the transaction.
     * @return {void}
     */
    _processRedirectFlow(providerCode, paymentOptionId, paymentMethodCode, processingValues) {
        if (providerCode !== 'payphone') {
            return super._processRedirectFlow(...arguments);
        }

        // Extract the redirect URL from the rendered form HTML.
        const div = document.createElement('div');
        div.innerHTML = processingValues['redirect_form_html'];
        const redirectForm = div.querySelector('form');
        const redirectUrl = redirectForm?.getAttribute('action');

        if (redirectUrl) {
            // Use window.location.href to ensure the Referer header is sent.
            window.location.href = redirectUrl;
        } else {
            // Fallback to the default behavior if no URL is found.
            super._processRedirectFlow(...arguments);
        }
    }
});
