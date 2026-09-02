/** @odoo-module **/
import publicWidget from "@web/legacy/js/public/public_widget";

publicWidget.registry.PaymentStripeFeeWidget = publicWidget.Widget.extend({
    selector: '#o_payment_form',
    events: {
        'change input[name="o_payment_radio"]': '_onPaymentMethodChange',
    },

    start: async function () {
        const result = await this._super.apply(this, arguments);
        this._cacheOriginalAmountTexts();
        this._toggleStripeBanner();
        return result;
    },

    _cacheOriginalAmountTexts() {
        const amountNodes = this._getAmountNodes();
        amountNodes.forEach((node) => {
            if (!node.dataset.stripeOriginalText) {
                node.dataset.stripeOriginalText = node.textContent;
            }
        });
    },

    _getAmountNodes() {
        return document.querySelectorAll('.total_amount, .oe_currency_value, .o_amount_total');
    },

    _extractBaseAmount() {
        const formAmount = parseFloat(this.el.dataset.amount || '0');
        if (!isNaN(formAmount) && formAmount > 0) {
            return formAmount;
        }

        const firstAmountNode = this._getAmountNodes()[0];
        if (!firstAmountNode) {
            return 0;
        }
        const raw = (firstAmountNode.dataset.stripeOriginalText || firstAmountNode.textContent || '').replace(/[^0-9.,]/g, '');
        const normalized = raw.lastIndexOf(',') > raw.lastIndexOf('.')
            ? raw.replace(/\./g, '').replace(',', '.')
            : raw.replace(/,/g, '');
        return parseFloat(normalized) || 0;
    },

    _formatAmount(amount) {
        return amount.toFixed(2);
    },

    _updateDisplayedAmounts(amount) {
        const formattedAmount = this._formatAmount(amount);
        this._getAmountNodes().forEach((node) => {
            node.textContent = formattedAmount;
        });
    },

    _restoreDisplayedAmounts() {
        this._getAmountNodes().forEach((node) => {
            if (node.dataset.stripeOriginalText) {
                node.textContent = node.dataset.stripeOriginalText;
            }
        });
    },

    _getSelectedPaymentInput() {
        return this.el.querySelector('input[name="o_payment_radio"]:checked');
    },

    _toggleStripeBanner() {
        const warningDiv = document.querySelector('#stripe-fee-warning');
        const amountSpan = document.querySelector('#stripe-subtotal');
        const totalSpan = document.querySelector('#stripe-total');
        const selected = this._getSelectedPaymentInput();
        const feeAmount = document.querySelector('#stripe-fee-amount');
        const feePercentage = selected ? parseFloat(selected.dataset.stripeFeePercentage || '0') : 0;
        const isStripe = selected && selected.dataset.providerCode === 'stripe' && feePercentage > 0;
        const baseAmount = this._extractBaseAmount();

        if (!warningDiv) {
            return;
        }

        if (!isStripe) {
            warningDiv?.classList.add('d-none');
            this._restoreDisplayedAmounts();
            return;
        }

        const feeValue = baseAmount * (feePercentage / 100);
        const totalValue = baseAmount + feeValue;
        this._updateDisplayedAmounts(totalValue);

        if (feeAmount) {
            feeAmount.textContent = this._formatAmount(feeValue);
        }

        if(amountSpan) {
            amountSpan.textContent = this._formatAmount(baseAmount);
        }

        if(totalSpan){
            totalSpan.textContent = this._getAmountNodes()[0].textContent;
        }

        warningDiv.classList.remove('d-none');
    },

    async _onPaymentMethodChange(ev) {
        this._toggleStripeBanner();
    }
});
