# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

from odoo.addons.payment import utils as payment_utils
from odoo.addons.payphone import const

_logger = logging.getLogger(__name__)

PAYPHONE_FEE_SECTION_NAME = 'Fee Payphone'


class PaymentTransaction(models.Model):
    _inherit = 'payment.transaction'

    amount_service = fields.Monetary(
        string="Service Amount",
        currency_field='currency_id',
        help="Original amount before the Payphone fee was added.",
    )
    payphone_fee = fields.Monetary(
        string="Payphone Fee",
        currency_field='currency_id',
        help="The Payphone processing fee added to the transaction.",
    )

    # === Action methods ===#

    def _get_specific_rendering_values(self, processing_values):
        """Override to return Payphone-specific rendering values.

        This calls the Payphone Prepare API to obtain the redirect URL for the
        hosted payment page. The returned URL is used in the redirect form template.

        :param dict processing_values: The generic processing values of the transaction.
        :return: The dict of provider-specific rendering values.
        :rtype: dict
        """
        res = super()._get_specific_rendering_values(processing_values)
        if self.provider_code != 'payphone':
            return res

        base_url = self.provider_id.get_base_url()

        # Payphone expects amounts in cents (integer)
        amount_cents = payment_utils.to_minor_currency_units(
            self.amount, self.currency_id
        )

        payload = {
            'amount': amount_cents,
            'amountWithoutTax': amount_cents,
            'amountWithTax': 0,
            'tax': 0,
            'service': 0,
            'tip': 0,
            'clientTransactionId': self.reference,
            'currency': 'USD',
            'storeId': self.provider_id.payphone_store_id,
            'reference': self.reference,
            'responseUrl': f'{base_url}{const.RETURN_URL}',
            'cancellationUrl': f'{base_url}{const.CANCEL_URL}',
        }

        # Add partner info if available (Payphone uses these to pre-fill forms)
        # Note: phoneNumber is intentionally omitted to let the user enter it
        # on the Payphone payment page, avoiding validation errors from
        # incorrectly formatted numbers stored in Odoo.
        if self.partner_id:
            if self.partner_id.email:
                payload['email'] = self.partner_id.email
            if self.partner_id.vat:
                payload['documentId'] = self.partner_id.vat

        result = self.provider_id._payphone_make_request(
            '/button/Prepare', payload=payload
        )

        pay_with_card = result.get('payWithCard')
        if not pay_with_card:
            error_msg = result.get('message', 'Unknown error')
            _logger.error("Payphone Prepare error: %s", result)
            raise ValidationError(_(
                "Payphone error: %(error)s", error=error_msg
            ))

        # The redirect form template renders a simple GET redirect to the
        # Payphone hosted payment page.
        return {
            'api_url': pay_with_card,
        }

    # === Business methods ===#

    @api.model
    def _extract_reference(self, provider_code, payment_data):
        """Override to extract the transaction reference from Payphone data.

        :param str provider_code: The code of the provider that handled the tx.
        :param dict payment_data: The payment data sent by the provider.
        :return: The transaction reference.
        :rtype: str
        """
        if provider_code != 'payphone':
            return super()._extract_reference(provider_code, payment_data)

        reference = payment_data.get('clientTransactionId')
        if not reference:
            raise ValidationError(_(
                "Payphone: No transaction reference found in the notification data."
            ))
        return reference

    def _extract_amount_data(self, payment_data):
        """Override to extract amount data from the Payphone confirmation response.

        :param dict payment_data: The payment data sent by the provider.
        :return: The amount data dict or None to skip validation.
        :rtype: dict | None
        """
        if self.provider_code != 'payphone':
            return super()._extract_amount_data(payment_data)

        amount = payment_data.get('amount')
        if amount is not None:
            return {
                'amount': payment_utils.to_major_currency_units(
                    amount, self.currency_id
                ),
                'currency_code': payment_data.get('currency', 'USD'),
            }
        # If amount is not in the data, skip validation
        return None

    def _apply_updates(self, payment_data):
        """Override to process the transaction based on Payphone confirmation data.

        This method is called by `_process()` after the payment data has been
        verified. It updates the transaction state based on the Payphone
        statusCode.

        :param dict payment_data: The verified payment data from Payphone.
        :return: None
        """
        if self.provider_code != 'payphone':
            return super()._apply_updates(payment_data)

        # Update the provider reference
        transaction_id = payment_data.get('transactionId')
        payphone_id = payment_data.get('id', payment_data.get('payphone_id'))
        self.provider_reference = str(transaction_id or payphone_id or '')

        # Update the payment method if card info is available
        card_brand = payment_data.get('cardBrand', '')
        if card_brand:
            payment_method = self.env['payment.method']._get_from_code('card')
            if payment_method:
                self.payment_method_id = payment_method

        # Map the Payphone statusCode to Odoo transaction state
        status_code = payment_data.get('statusCode')
        transaction_status = payment_data.get('transactionStatus', '')

        if status_code in const.PAYMENT_STATUS_MAPPING['done']:
            self._set_done()
            _logger.info(
                "Payphone payment approved for tx %s (auth: %s)",
                self.reference,
                payment_data.get('authorizationCode'),
            )
        elif status_code in const.PAYMENT_STATUS_MAPPING['canceled']:
            self._payphone_remove_fee_section(self.sale_order_ids)
            self._set_canceled(state_message=_(
                "Payment was rejected by Payphone: %(status)s",
                status=transaction_status,
            ))
        else:
            self._set_pending(state_message=_(
                "Payment is pending on Payphone: %(status)s",
                status=transaction_status,
            ))

    def _set_done(self, **kwargs):
        """Al confirmarse el pago se agrega la linea del fee a la orden (antes no, para
        no dejarla huerfana en borrador). Asi la factura generada desde la orden la
        incluye. Para facturas directas no hay orden y el fee va por write-off."""
        result = super()._set_done(**kwargs)
        self._payphone_add_fee_lines_on_done()
        return result

    def _payphone_add_fee_lines_on_done(self):
        for tx in self.filtered(lambda t: t.provider_code == 'payphone'):
            orders = tx.sale_order_ids
            if not orders or tx.currency_id.is_zero(tx.payphone_fee):
                continue
            fee_product = tx._payphone_fee_product()
            if not fee_product:
                continue
            fee_rate = tx.provider_id.payphone_fee_percentage / 100.0
            for order in orders:
                fee_base, dummy_total, dummy_line = tx._payphone_order_fee(
                    order, fee_product, fee_rate)
                if fee_base:
                    tx._payphone_add_fee_section(order, fee_base, fee_product)

    @api.model_create_multi
    def create(self, values_list):
        """Calcula el monto a cobrar (servicio + fee) al crear la transaccion.

        - Orden de venta: se calcula el total con fee (formula inversa + IVA), pero la
          linea del fee NO se agrega aqui; se agrega al confirmar el pago (_set_done),
          para no dejar lineas huerfanas si el proveedor falla o el cliente abandona.
        - Factura directa (sin orden): el fee se asienta como ajuste en el pago (write-off).
        - Otro metodo de pago: se limpia cualquier seccion de fee (cambio de metodo).

        El fee usa la formula inversa con IVA para que el merchant reciba el monto
        original tras la deduccion del porcentaje de Payphone.
        """
        default_product = self._payphone_fee_product()

        for values in values_list:
            provider_id = values.get('provider_id')
            if not provider_id:
                continue
            provider = self.env['payment.provider'].browse(provider_id)
            fee_product = provider.payphone_fee_product_id or default_product
            orders = self.env['sale.order'].sudo().browse(
                self._payphone_order_ids_from_values(values)
            ).exists()

            is_payphone_fee = (
                provider.code == 'payphone'
                and provider.payphone_fee_percentage > 0
                and bool(fee_product)
            )
            if not is_payphone_fee:
                # Otro metodo (o Payphone sin fee): se limpia la seccion para no
                # chocar con el metodo elegido (cambio de metodo de pago).
                self._payphone_remove_fee_section(orders)
                continue

            fee_rate = provider.payphone_fee_percentage / 100.0

            if not orders:
                # Sin orden de venta: factura de cliente creada en account.move.
                # Se cobra el fee adicional; se asienta como ajuste en el pago (write-off).
                self._payphone_apply_invoice_fee(values, provider, fee_product, fee_rate)
                continue

            # Pago de orden de venta: el monto a cobrar incluye el fee, pero la linea
            # NO se agrega aqui (en borrador). Se agrega al confirmar el pago en
            # _set_done, para no dejar lineas huerfanas si el proveedor falla o el
            # cliente abandona. El total se calcula con el motor de impuestos
            # (compute_all) para que coincida con la linea cuando se cree al confirmar.
            merchant_total = 0.0
            fee_base_total = 0.0
            total_charge = 0.0
            for order in orders:
                fee_base, original_total, fee_line_total = self._payphone_order_fee(
                    order, fee_product, fee_rate)
                merchant_total += original_total
                fee_base_total += fee_base
                total_charge += original_total + fee_line_total
            values['amount'] = round(total_charge, 2)
            values['amount_service'] = round(merchant_total, 2)
            values['payphone_fee'] = round(fee_base_total, 2)

        return super().create(values_list)

    def _create_payment(self, **extra_create_values):
        """Cobra el fee de Payphone en facturas directas (sin orden) sin alterar el
        total de la factura: mediante una linea de ajuste (write-off) el fee se asienta
        en la cuenta de ingreso del producto y la contrapartida concilia con la factura
        -> esta queda "En proceso de pago" conservando su total original.
        """
        fee_writeoff_vals = self._payphone_fee_get_writeoff_vals()
        if fee_writeoff_vals:
            write_off_line_vals = list(extra_create_values.get('write_off_line_vals') or [])
            write_off_line_vals.extend(fee_writeoff_vals)
            extra_create_values['write_off_line_vals'] = write_off_line_vals
        return super()._create_payment(**extra_create_values)

    def _payphone_fee_get_writeoff_vals(self):
        """Linea de ajuste para registrar el fee al conciliar una factura directa.

        Solo aplica a cobros (inbound) de Payphone con fee y factura asociada SIN orden
        (si hay orden, el fee ya va como linea en la SO). La cuenta es la de ingreso del
        producto del fee. El importe es la diferencia cobrada (fee + su IVA)."""
        self.ensure_one()
        if self.provider_code != 'payphone' or self.amount <= 0:
            return []
        if self.sale_order_ids or not self.invoice_ids:
            return []
        if self.currency_id.is_zero(self.payphone_fee):
            return []
        fee_gross = self.amount - self.amount_service
        if self.currency_id.is_zero(fee_gross):
            return []

        company = self.provider_id.company_id or self.env.company
        account = self._payphone_fee_income_account(self._payphone_fee_product(), company)
        if not account:
            _logger.warning(
                "No se registro el fee de Payphone de la transaccion %s: "
                "el producto del fee no tiene cuenta de ingreso.",
                self.reference,
            )
            return []

        amount_currency = -fee_gross
        balance = self.currency_id._convert(
            amount_currency, company.currency_id, company,
            fields.Date.context_today(self),
        )
        return [{
            'name': _("Recargo por procesamiento Payphone"),
            'account_id': account.id,
            'partner_id': self.partner_id.commercial_partner_id.id,
            'currency_id': self.currency_id.id,
            'amount_currency': amount_currency,
            'balance': balance,
        }]

    def _payphone_fee_product(self):
        """Producto del fee: el configurado en el proveedor, o el por defecto (xmlid)."""
        product = self.provider_id[:1].payphone_fee_product_id
        return product or self.env.ref(
            'payphone.product_payphone_fee', raise_if_not_found=False
        )

    def _payphone_order_fee(self, order, fee_product, fee_rate):
        """Calcula el fee de una orden con la formula inversa e IVA mapeado por la
        posicion fiscal. Devuelve (fee_base, original_total, fee_line_total):
        - fee_base: precio unitario (sin IVA) de la linea del fee.
        - original_total: total de la orden sin secciones/notas ni la linea del fee.
        - fee_line_total: total de la linea del fee CON IVA (lo que sumara a la orden).
        El total se obtiene con compute_all para que coincida con la linea real."""
        fee_products = self._payphone_fee_products()
        # Si ya hay una linea de fee FACTURADA no se puede reemplazar al confirmar; no se
        # cobra el fee de nuevo (la SO no usa write-off) para no sobrepagar.
        fee_lines = order.order_line.filtered(lambda l: l.product_id in fee_products)
        original_total = sum(order.order_line.filtered(
            lambda l: not l.display_type and l.product_id not in fee_products
        ).mapped('price_total'))
        if fee_lines.invoice_lines or not original_total:
            return 0.0, original_total, 0.0

        taxes = fee_product.taxes_id
        if order.fiscal_position_id:
            taxes = order.fiscal_position_id.map_tax(taxes)
        tax_rate = sum(taxes.mapped('amount')) / 100.0 if taxes else 0.0

        effective_rate = fee_rate * (1 + tax_rate)
        if effective_rate >= 1:
            _logger.warning(
                "Invalid Payphone fee configuration (effective_rate=%s)", effective_rate,
            )
            return 0.0, original_total, 0.0

        total_to_charge = original_total / (1 - effective_rate)
        fee_with_tax = total_to_charge - original_total
        fee_base = round(fee_with_tax / (1 + tax_rate) if tax_rate else fee_with_tax, 2)
        # Mismo partner que usa sale.order.line (partner_shipping_id) para que el total
        # de la linea del fee coincida EXACTO con el monto cobrado y la factura concilie.
        fee_line_total = taxes.compute_all(
            fee_base, order.currency_id, 1.0, product=fee_product,
            partner=order.partner_shipping_id or order.partner_id,
        )['total_included']
        return fee_base, original_total, fee_line_total

    def _payphone_fee_products(self):
        """Todos los productos que pueden ser linea de fee Payphone: el por defecto
        y los configurados en cualquier proveedor Payphone (para limpiar tambien los
        personalizados)."""
        products = self.env['payment.provider'].search(
            [('code', '=', 'payphone')]).mapped('payphone_fee_product_id')
        default = self.env.ref('payphone.product_payphone_fee', raise_if_not_found=False)
        if default:
            products |= default
        return products

    def _payphone_fee_income_account(self, fee_product, company):
        """Cuenta de ingreso donde se asienta el fee (write-off). Misma resolucion para
        decidir el cobro en create() y para crear la linea en _create_payment, de modo
        que no se cobre el fee si no hay cuenta (evita sobrepago)."""
        if not fee_product or not company:
            return self.env['account.account']
        return fee_product.with_company(company)._get_product_accounts().get('income') \
            or self.env['account.account']

    @api.model
    def _payphone_command_ids(self, commands):
        """Extrae los ids de un valor x2many recibido en create (formatos (4, id) / (6, 0, ids))."""
        ids = []
        for cmd in commands or []:
            if isinstance(cmd, (list, tuple)) and cmd:
                if cmd[0] == 6 and len(cmd) > 2:    # (6, 0, [ids])
                    ids.extend(cmd[2])
                elif cmd[0] == 4 and len(cmd) > 1:  # (4, id)
                    ids.append(cmd[1])
            elif isinstance(cmd, int):
                ids.append(cmd)
        return ids

    @api.model
    def _payphone_order_ids_from_values(self, values):
        return self._payphone_command_ids(values.get('sale_order_ids'))

    def _payphone_fee_eligible_invoices(self, values):
        """Facturas de cliente (out_invoice) que aun no tienen la linea del fee.

        Aplica tanto a facturas creadas directamente en account.move como a las
        generadas desde una orden de venta (mientras el fee no este ya en sus lineas),
        porque al pagar la FACTURA no hay forma de meter el fee en la orden. La unica
        condicion para no duplicar es que el fee no exista ya en las lineas."""
        invoice_ids = self._payphone_command_ids(values.get('invoice_ids'))
        if not invoice_ids:
            return self.env['account.move']
        invoices = self.env['account.move'].browse(invoice_ids).exists()
        # Cualquier producto de fee Payphone (por defecto + personalizados) ya en la factura.
        fee_products = self._payphone_fee_products()
        return invoices.filtered(lambda inv: (
            inv.move_type == 'out_invoice'
            and not (fee_products & inv.invoice_line_ids.product_id)
        ))

    def _payphone_apply_invoice_fee(self, values, provider, fee_product, fee_rate):
        """Recarga el fee (formula inversa con IVA) sobre el monto a pagar de una factura
        directa, sin modificar la factura. El fee se asienta luego en el pago (write-off)."""
        invoices = self._payphone_fee_eligible_invoices(values)
        base = values.get('amount', 0.0)
        if not invoices or not base:
            return

        # Solo se cobra el fee si el write-off podra asentarse (hay cuenta de ingreso);
        # de lo contrario no se sube el monto, para no sobrepagar la factura.
        if not self._payphone_fee_income_account(fee_product, provider.company_id):
            _logger.warning(
                "No se cobro el fee de Payphone en la factura: el producto del fee "
                "no tiene cuenta de ingreso (proveedor %s).", provider.display_name,
            )
            return

        taxes = fee_product.taxes_id
        fp = invoices[:1].fiscal_position_id
        if fp:
            taxes = fp.map_tax(taxes)
        tax_rate = sum(taxes.mapped('amount')) / 100.0 if taxes else 0.0

        effective_rate = fee_rate * (1 + tax_rate)
        if effective_rate >= 1:
            _logger.warning(
                "Invalid Payphone fee configuration (effective_rate=%s)", effective_rate,
            )
            return

        total_to_charge = base / (1 - effective_rate)
        fee_with_tax = total_to_charge - base
        fee_base = fee_with_tax / (1 + tax_rate) if tax_rate else fee_with_tax
        values['amount'] = round(total_to_charge, 2)
        values['amount_service'] = round(base, 2)
        values['payphone_fee'] = round(fee_base, 2)

    def _payphone_add_fee_section(self, orders, fee_base, fee_product=None):
        """Crea, siempre al final, la seccion "Fee Payphone" + la linea del fee (con IVA).

        Idempotente: quita la seccion previa y la recrea al final, para que quede
        aislada y no choque con las secciones, notas u opcionales de la cotizacion.
        """
        fee_product = fee_product or self._payphone_fee_product()
        if not fee_product:
            _logger.warning("Payphone fee product not found. Skipping fee section.")
            return

        SaleOrderLine = self.env['sale.order.line'].sudo()
        for order in orders:
            self._payphone_remove_fee_section(order)
            # Si quedo una linea del fee ya facturada (no se pudo borrar), no se
            # agrega otra para no cobrar el fee dos veces.
            if order.order_line.filtered(lambda l, fp=fee_product: l.product_id == fp):
                continue
            next_sequence = max(order.order_line.mapped('sequence') or [0]) + 1
            SaleOrderLine.create([
                {
                    'order_id': order.id,
                    'display_type': 'line_section',
                    'name': PAYPHONE_FEE_SECTION_NAME,
                    'sequence': next_sequence,
                },
                {
                    'order_id': order.id,
                    'product_id': fee_product.id,
                    'name': fee_product.name,
                    'product_uom_qty': 1,
                    'price_unit': fee_base,
                    'sequence': next_sequence + 1,
                },
            ])

    def _payphone_remove_fee_section(self, orders):
        """Quita la seccion "Fee Payphone" y su linea (omitiendo lineas ya facturadas)."""
        if not orders:
            return
        fee_products = self._payphone_fee_products()
        section_clause = ['&', ('display_type', '=', 'line_section'), ('name', '=', PAYPHONE_FEE_SECTION_NAME)]
        if fee_products:
            domain = [('order_id', 'in', orders.ids), '|'] + section_clause + [('product_id', 'in', fee_products.ids)]
        else:
            domain = [('order_id', 'in', orders.ids)] + section_clause
        lines = self.env['sale.order.line'].sudo().search(domain).filtered(
            lambda l: not l.invoice_lines
        )
        if lines:
            lines.unlink()
