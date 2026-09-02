/** @odoo-module **/
import publicWidget from "@web/legacy/js/public/public_widget";

publicWidget.registry.PayphoneFeeWidget = publicWidget.Widget.extend({
    selector: '#o_payment_form',
    events: {
        'change input[name="o_payment_radio"]': '_onPaymentMethodChange',
    },

    start: async function () {
        const result = await this._super.apply(this, arguments);
        this._togglePayphoneBanner();
        return result;
    },

    _getBaseAmount() {
        const formAmount = parseFloat(this.el.dataset.amount || '0');
        return !isNaN(formAmount) && formAmount > 0 ? formAmount : 0;
    },

    _getSelectedPaymentInput() {
        return this.el.querySelector('input[name="o_payment_radio"]:checked');
    },

    _togglePayphoneBanner() {
        const warningDiv = document.querySelector('#payphone-fee-warning');
        if (!warningDiv) {
            return;
        }

        const feeAmount = document.querySelector('#payphone-fee-amount');
        const selected = this._getSelectedPaymentInput();
        const effectiveRate = selected ? parseFloat(selected.dataset.payphoneEffectiveRate || '0') : 0;
        // El fee solo aplica a Payphone; effectiveRate solo es > 0 para ese metodo.
        const isPayphone = !!selected && effectiveRate > 0 && effectiveRate < 1;

        if (!isPayphone) {
            warningDiv.classList.add('d-none');
            return;
        }

        // Si la factura ya trae la linea del fee, su valor (con IVA) viene del servidor;
        // se muestra tal cual (es el de la linea) y NO se recalcula sobre el total.
        const existingFee = parseFloat(this.el.dataset.payphoneExistingFee || '0');
        const lead = document.querySelector('#payphone-fee-lead');
        let feeValue;
        if (existingFee > 0) {
            feeValue = existingFee;
            if (lead) {
                lead.textContent = 'Esta factura ya incluye un recargo de ';
            }
        } else {
            // Formula inversa (igual que en el servidor): total = base / (1 - tasa efectiva).
            const baseAmount = this._getBaseAmount();
            feeValue = baseAmount / (1 - effectiveRate) - baseAmount;
            if (lead) {
                lead.textContent = 'Este metodo agrega un valor adicional de ';
            }
        }

        if (feeAmount) {
            feeAmount.textContent = feeValue.toFixed(2);
        }

        warningDiv.classList.remove('d-none');
    },

    _onPaymentMethodChange() {
        this._togglePayphoneBanner();
    },
});
