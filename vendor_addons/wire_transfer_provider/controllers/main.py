import base64
import binascii

from odoo import _
from odoo.addons.payment import utils as payment_utils
from odoo.addons.payment.controllers.post_processing import PaymentPostProcessing
from odoo.addons.portal.controllers.portal import CustomerPortal
from odoo.exceptions import AccessError, MissingError, ValidationError
from odoo.http import request, route


class WireTransferProviderController(CustomerPortal):
    _process_url = '/payment/wire_transfer_provider/process'
    _submit_url = '/payment/wire_transfer_provider/submit'
    _receipt_url = '/payment/wire_transfer_provider/receipt/<int:tx_id>'
    _upload_url = '/payment/wire_transfer_provider/upload_receipt'

    @route(_process_url, type='http', auth='public', methods=['POST'], csrf=False)
    def process_transaction(self, **post):
        try:
            request.env['payment.transaction'].sudo()._process('wire_transfer_provider', post)
        except ValidationError as err:
            request.session['wire_transfer_flash_level'] = 'error'
            request.session['wire_transfer_flash_message'] = str(err)
            return request.redirect('/payment/status')
        tx = request.env['payment.transaction'].sudo().search([
            ('reference', '=', (post.get('reference') or '').strip()),
            ('provider_code', '=', 'wire_transfer_provider'),
        ], limit=1)
        return request.redirect(self._get_portal_redirect_url(tx))

    @route(_submit_url, type='jsonrpc', auth='public', website=True)
    def submit_transaction(
        self,
        provider_id,
        reference,
        wire_reference='',
        receipt_filename='',
        receipt_content='',
        receipt_mimetype='',
    ):
        provider = request.env['payment.provider'].sudo().browse(int(provider_id)).exists()
        if not provider or provider.code != 'wire_transfer_provider':
            raise ValidationError(_('Proveedor de pago invalido.'))

        tx = request.env['payment.transaction'].sudo().search([
            ('reference', '=', (reference or '').strip()),
            ('provider_code', '=', 'wire_transfer_provider'),
        ], limit=1)
        if not tx:
            raise ValidationError(_('No se encontro la transaccion de pago.'))

        try:
            tx = self._authorize_transaction(tx)
        except (AccessError, MissingError):
            raise ValidationError(_('No tienes permisos para actualizar esta transaccion.'))

        file_content = b''
        if receipt_content:
            try:
                file_content = base64.b64decode(receipt_content, validate=True)
            except (ValueError, TypeError, binascii.Error) as err:
                raise ValidationError(_('El archivo del comprobante no es valido.')) from err

        tx._wire_apply_customer_inputs(
            wire_reference=wire_reference,
            filename=receipt_filename,
            mimetype=receipt_mimetype,
            content=file_content or False,
        )
        tx._process('wire_transfer_provider', {'reference': tx.reference})
        if file_content:
            tx._wire_notify_receipt_uploaded()
        PaymentPostProcessing.monitor_transaction(tx)
        return {'redirect_url': '/payment/status'}

    @route(_receipt_url, type='http', auth='public', methods=['GET'], website=True)
    def get_receipt(
        self, tx_id, order_id=None, order_access_token=None, invoice_id=None,
        invoice_access_token=None, access_token=None, download='true', **kwargs
    ):
        tx = request.env['payment.transaction'].sudo().browse(tx_id)
        if not tx.exists() or tx.provider_code != 'wire_transfer_provider' or not tx.wire_receipt_file:
            return request.not_found()

        try:
            tx = self._get_authorized_tx(
                tx,
                order_id=order_id,
                order_token=order_access_token,
                invoice_id=invoice_id,
                invoice_token=invoice_access_token,
                access_token=access_token,
            )
        except (AccessError, MissingError):
            return request.not_found()

        try:
            content = base64.b64decode(tx.wire_receipt_file)
        except (ValueError, TypeError, binascii.Error):
            return request.not_found()

        disposition = 'attachment' if str(download).lower() == 'true' else 'inline'
        filename = tx._wire_sanitize_filename(tx.wire_receipt_filename or 'comprobante')
        headers = [
            ('Content-Type', tx.wire_receipt_mimetype or 'application/octet-stream'),
            ('Content-Length', str(len(content))),
            ('Content-Disposition', f'{disposition}; filename="{filename}"'),
        ]
        return request.make_response(content, headers=headers)

    @route(_upload_url, type='http', auth='public', methods=['POST'], website=True)
    def upload_receipt(self, **post):
        reference = (post.get('reference') or '').strip()
        access_token = (post.get('access_token') or '').strip()
        order_id = post.get('order_id')
        order_token = post.get('order_access_token')
        invoice_id = post.get('invoice_id')
        invoice_token = post.get('invoice_access_token')
        wire_reference = (post.get('wire_reference') or '').strip()
        tx = request.env['payment.transaction'].sudo().search([
            ('reference', '=', reference),
            ('provider_code', '=', 'wire_transfer_provider'),
        ], limit=1)
        if not tx:
            return request.redirect('/payment/status')

        try:
            tx = self._get_authorized_tx(
                tx,
                order_id=order_id,
                order_token=order_token,
                invoice_id=invoice_id,
                invoice_token=invoice_token,
                access_token=access_token,
            )
        except (AccessError, MissingError):
            return request.redirect('/payment/status')

        upload = request.httprequest.files.get('wire_receipt_file')
        content = False
        filename = ''
        mimetype = ''
        if upload and upload.filename:
            content = upload.read()
            filename = upload.filename
            mimetype = upload.mimetype

        try:
            tx._wire_apply_customer_inputs(
                wire_reference=wire_reference,
                filename=filename,
                mimetype=mimetype,
                content=content,
            )
        except ValidationError as err:
            request.session['wire_transfer_flash_level'] = 'error'
            request.session['wire_transfer_flash_message'] = str(err)
            return request.redirect(self._get_portal_redirect_url(tx))
        if content:
            tx._wire_notify_receipt_uploaded()
        request.session['wire_transfer_flash_level'] = 'success'
        request.session['wire_transfer_flash_message'] = _('Comprobante guardado correctamente.')
        return request.redirect(self._get_portal_redirect_url(tx))

    @staticmethod
    def _get_portal_redirect_url(tx):
        if tx and tx.sale_order_ids:
            return tx.sale_order_ids[:1].get_portal_url()
        if tx and tx.invoice_ids:
            return tx.invoice_ids[:1].get_portal_url()
        return '/payment/status'

    def _get_authorized_tx(
        self, tx, order_id=None, order_token='', invoice_id=None, invoice_token='', access_token=''
    ):
        if request.env.user._is_internal():
            return tx

        order_id = self._to_int(order_id)
        invoice_id = self._to_int(invoice_id)
        order_token = (order_token or '').strip()
        invoice_token = (invoice_token or '').strip()
        access_token = (access_token or '').strip()

        if order_id:
            order = self._document_check_access('sale.order', order_id, access_token=order_token or None)
            if tx in order.transaction_ids:
                return tx
        if invoice_id:
            invoice = self._document_check_access('account.move', invoice_id, access_token=invoice_token or None)
            if tx in invoice.transaction_ids:
                return tx

        return self._authorize_transaction(tx, access_token=access_token)

    @staticmethod
    def _to_int(value):
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return 0

    def _authorize_transaction(self, tx, access_token=None):
        if request.env.user._is_internal():
            return tx
        access_token = (access_token or '').strip()
        if not access_token:
            raise AccessError(_('Missing access token.'))
        partner_id = tx.partner_id.id if tx.partner_id else 0
        amount = tx.amount or 0.0
        currency_id = tx.currency_id.id if tx.currency_id else 0
        if not payment_utils.check_access_token(access_token, partner_id, amount, currency_id):
            raise AccessError(_('Invalid access token.'))
        return tx
