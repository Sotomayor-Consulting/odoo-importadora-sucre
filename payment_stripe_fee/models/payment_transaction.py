import logging

from odoo import _, api, fields, models


_logger = logging.getLogger(__name__)

STRIPE_FEE_SECTION_NAME = 'Fee Stripe'


class PaymentTransaction(models.Model):
    _inherit = 'payment.transaction'

    amount_service = fields.Monetary(string="Monto del servicio", currency_field='currency_id')
    stripe_fee = fields.Monetary(string="Fee de Stripe", currency_field='currency_id')


    @api.model_create_multi
    def create(self, values_list):
        for values in values_list:
            provider_id = values.get('provider_id')
            if not provider_id:
                continue
            provider = self.env['payment.provider'].browse(provider_id)
            if provider.code != 'stripe' or provider.stripe_fee_percentage <= 0:
                continue
            # Si la factura a cobrar ya incluye la linea del fee (heredada de la orden
            # de venta), no se recarga de nuevo para evitar cobrar el fee dos veces.
            if self._stripe_fee_already_in_invoices(values):
                continue
            # Pago de factura directa (con factura y sin orden): solo se cobra el fee si
            # el write-off podra asentarse (hay cuenta de ingreso); de lo contrario no se
            # sube el monto, para no sobrepagar la factura.
            invoice_ids = self._stripe_fee_extract_command_ids(values.get('invoice_ids'))
            order_ids = self._stripe_fee_extract_command_ids(values.get('sale_order_ids'))
            if invoice_ids and not order_ids:
                fee_product = provider.stripe_fee_product_id or self.env.ref(
                    'payment_stripe_fee.product_stripe_fee', raise_if_not_found=False)
                if not self._stripe_fee_income_account(fee_product, provider.company_id):
                    _logger.warning(
                        "No se cobro el fee de Stripe en la factura: el producto del fee "
                        "no tiene cuenta de ingreso (proveedor %s).", provider.display_name,
                    )
                    continue
            # Pago de orden con linea de fee previa: se excluye ese fee de la base para no
            # calcular fee sobre fee (snowball). Si esa linea ya esta FACTURADA no se puede
            # reemplazar al confirmar -> no se cobra el fee de nuevo (la SO no usa write-off),
            # para no sobrepagar.
            existing_fee = 0.0
            if order_ids:
                orders = self.env['sale.order'].browse(order_ids).exists()
                fee_lines = orders.order_line.filtered(
                    lambda l: l.product_id in self._stripe_fee_products())
                if fee_lines.invoice_lines:
                    continue
                existing_fee = sum(fee_lines.mapped('price_total'))
            original_amount = max(values.get('amount', 0.0) - existing_fee, 0.0)
            fee = original_amount * (provider.stripe_fee_percentage / 100.0)

            values['amount_service'] = original_amount
            values['stripe_fee'] = fee
            values['amount'] = original_amount + fee
        records = super().create(values_list)
        # En borrador solo se LIMPIA la seccion si se cambio de metodo; la seccion se
        # agrega al confirmar el pago (_set_done), para no dejar lineas huerfanas si el
        # proveedor falla o el cliente abandona.
        records._sync_stripe_fee_sale_order_lines()
        return records

    def _stripe_fee_already_in_invoices(self, values):
        invoice_ids = self._stripe_fee_extract_command_ids(values.get('invoice_ids'))
        if not invoice_ids:
            return False
        fee_products = self._stripe_fee_products()
        if not fee_products:
            return False
        invoices = self.env['account.move'].browse(invoice_ids).exists()
        return any(fee_products & inv.invoice_line_ids.product_id for inv in invoices)

    @api.model
    def _stripe_fee_extract_command_ids(self, commands):
        """Extrae los ids de un valor x2many recibido en create (formatos (4, id) / (6, 0, ids))."""
        if not commands:
            return []
        ids = []
        for command in commands:
            if isinstance(command, (list, tuple)) and command:
                code = command[0]
                if code == 4 and len(command) > 1:
                    ids.append(command[1])
                elif code == 6 and len(command) > 2 and command[2]:
                    ids.extend(command[2])
            elif isinstance(command, int):
                ids.append(command)
        return ids

    def _set_done(self, **kwargs):
        result = super()._set_done(**kwargs)
        # Al confirmar el pago se agrega la seccion del fee a la orden (antes no, para
        # no dejarla huerfana en borrador), antes de que se genere la factura.
        self._sync_stripe_fee_sale_order_lines(add_lines=True)
        return result

    def _set_authorized(self, **kwargs):
        result = super()._set_authorized(**kwargs)
        # Al autorizar, la orden se confirma (y puede facturarse antes de capturar), asi
        # que la linea del fee debe estar presente ya en ese momento.
        self._sync_stripe_fee_sale_order_lines(add_lines=True)
        return result

    def _set_canceled(self, *args, **kwargs):
        # state_message puede llegar posicional en el core (no es keyword-only), por eso
        # se reenvian *args ademas de **kwargs.
        result = super()._set_canceled(*args, **kwargs)
        # Pago anulado (p. ej. void tras autorizar): se quita la seccion del fee si se
        # habia agregado (omitiendo lineas ya facturadas).
        if 'sale.order.line' in self.env:
            for tx in self:
                if (tx.provider_code == 'stripe' and 'sale_order_ids' in tx._fields
                        and tx.sale_order_ids):
                    tx._remove_stripe_fee_section(tx.sale_order_ids)
        return result

    def _create_payment(self, **extra_create_values):
        """Cobra el fee de Stripe sin alterar el total de la factura.

        El pago se crea por el monto total (servicio + fee). Mediante una linea de
        ajuste (write-off) el fee se asienta en la cuenta configurada en el proveedor,
        de modo que la contrapartida por cobrar queda en el monto del servicio y concilia
        con la factura -> esta queda "En proceso de pago" conservando su total original.
        """
        fee_writeoff_vals = self._stripe_fee_get_writeoff_vals()
        if fee_writeoff_vals:
            write_off_line_vals = list(extra_create_values.get('write_off_line_vals') or [])
            write_off_line_vals.extend(fee_writeoff_vals)
            extra_create_values['write_off_line_vals'] = write_off_line_vals
        return super()._create_payment(**extra_create_values)

    def _stripe_fee_get_writeoff_vals(self):
        """Lineas de ajuste para registrar el fee al conciliar una factura.

        Solo aplica a cobros (inbound) de Stripe con fee y factura asociada. La cuenta
        es la de ingreso del producto del fee. Devuelve [] si no corresponde o si el
        producto no tiene cuenta (se registra una advertencia para no dejar la factura
        sobrepagada en silencio).
        """
        self.ensure_one()
        if self.provider_code != 'stripe' or self.amount <= 0:
            return []
        if self.currency_id.is_zero(self.stripe_fee) or not self.invoice_ids:
            return []

        company = self.provider_id.company_id or self.env.company
        account = self._stripe_fee_income_account(self._stripe_fee_product(), company)
        if not account:
            _logger.warning(
                "No se registro el fee de Stripe de la transaccion %s: "
                "el producto del fee no tiene cuenta de ingreso.",
                self.reference,
            )
            return []

        # Inbound: el fee reduce la contrapartida para que esta quede en el monto del
        # servicio (= total de la factura). Por eso el importe es negativo.
        amount_currency = -self.stripe_fee
        balance = self.currency_id._convert(
            amount_currency, company.currency_id, company,
            fields.Date.context_today(self),
        )
        return [{
            'name': _("Recargo por procesamiento Stripe"),
            'account_id': account.id,
            'partner_id': self.partner_id.commercial_partner_id.id,
            'currency_id': self.currency_id.id,
            'amount_currency': amount_currency,
            'balance': balance,
        }]

    def _sync_stripe_fee_sale_order_lines(self, add_lines=False):
        """Ajusta la seccion del fee en las ordenes segun el metodo de pago de cada tx.

        - Otro metodo de pago: elimina la seccion "Fee Stripe" (cambio de metodo).
        - Stripe con fee: agrega la seccion SOLO si add_lines=True (al confirmar el pago,
          _set_done). En create() (borrador) NO se agrega, para no dejar lineas huerfanas
          si el proveedor falla o el cliente abandona.
        """
        if 'sale.order.line' not in self.env:
            return

        for tx in self:
            if 'sale_order_ids' not in tx._fields:
                continue
            sale_orders = tx.sale_order_ids
            if not sale_orders:
                continue

            is_stripe_fee = tx.provider_code == 'stripe' and not tx.currency_id.is_zero(tx.stripe_fee)
            if is_stripe_fee:
                if add_lines:
                    tx._add_stripe_fee_section(sale_orders)
            else:
                tx._remove_stripe_fee_section(sale_orders)

    def _stripe_fee_product(self):
        self.ensure_one()
        return self.provider_id.stripe_fee_product_id or self.env.ref(
            'payment_stripe_fee.product_stripe_fee', raise_if_not_found=False)

    def _stripe_fee_income_account(self, fee_product, company):
        """Cuenta de ingreso donde se asienta el fee (write-off). Misma resolucion para
        decidir el cobro en create() y para crear la linea en _create_payment, de modo
        que no se cobre el fee si no hay cuenta (evita sobrepago)."""
        if not fee_product or not company:
            return self.env['account.account']
        return fee_product.with_company(company)._get_product_accounts().get('income') \
            or self.env['account.account']

    def _stripe_fee_products(self):
        """Todos los productos que pueden ser linea de fee: el por defecto y los
        configurados en cualquier proveedor Stripe (para limpiar tambien los
        personalizados)."""
        products = self.env['payment.provider'].search(
            [('code', '=', 'stripe')]).mapped('stripe_fee_product_id')
        default = self.env.ref('payment_stripe_fee.product_stripe_fee', raise_if_not_found=False)
        if default:
            products |= default
        return products

    def _add_stripe_fee_section(self, orders):
        self.ensure_one()
        fee_product = self._stripe_fee_product()
        if not fee_product:
            _logger.warning(
                'Stripe fee section skipped for transaction %s: no fee product configured.',
                self.reference,
            )
            return

        SaleOrderLine = self.env['sale.order.line']
        for order in orders:
            # Idempotente: se quita la seccion previa y se vuelve a crear al final.
            self._remove_stripe_fee_section(order)
            # Si quedo una linea del fee ya facturada (no se pudo borrar), no se
            # agrega otra para no cobrar el fee dos veces.
            if order.order_line.filtered(lambda l, fp=fee_product: l.product_id == fp):
                continue
            next_sequence = max(order.order_line.mapped('sequence') or [0]) + 1
            SaleOrderLine.create([
                {
                    'order_id': order.id,
                    'display_type': 'line_section',
                    'name': STRIPE_FEE_SECTION_NAME,
                    'sequence': next_sequence,
                },
                {
                    'order_id': order.id,
                    'product_id': fee_product.id,
                    'name': fee_product.name,
                    'product_uom_qty': 1.0,
                    'price_unit': self.stripe_fee,
                    'tax_ids': [(6, 0, [])],
                    'sequence': next_sequence + 1,
                },
            ])

    def _remove_stripe_fee_section(self, orders):
        self.ensure_one()
        fee_products = self._stripe_fee_products()
        section_clause = ['&', ('display_type', '=', 'line_section'), ('name', '=', STRIPE_FEE_SECTION_NAME)]
        if fee_products:
            domain = [('order_id', 'in', orders.ids), '|'] + section_clause + [('product_id', 'in', fee_products.ids)]
        else:
            domain = [('order_id', 'in', orders.ids)] + section_clause
        # No se tocan lineas ya facturadas para no romper la contabilidad.
        lines = self.env['sale.order.line'].search(domain).filtered(lambda l: not l.invoice_lines)
        if lines:
            lines.unlink()
