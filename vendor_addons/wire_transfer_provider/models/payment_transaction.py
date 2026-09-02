import base64
import binascii
import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class PaymentTransaction(models.Model):
    _inherit = 'payment.transaction'

    wire_receipt_file = fields.Binary(string='Comprobante de transferencia', attachment=True, copy=False)
    wire_receipt_filename = fields.Char(string='Nombre del comprobante', copy=False)
    wire_receipt_mimetype = fields.Char(string='Tipo MIME del comprobante', copy=False)
    wire_reference = fields.Char(string='Referencia de transferencia', copy=False)

    @staticmethod
    def _wire_detect_image_mimetype(content):
        if content.startswith(b'\x89PNG\r\n\x1a\n'):
            return 'image/png'
        if content.startswith(b'\xff\xd8\xff'):
            return 'image/jpeg'
        return False

    def _get_specific_rendering_values(self, processing_values):
        if self.provider_code != 'wire_transfer_provider':
            return super()._get_specific_rendering_values(processing_values)
        return {
            'api_url': '/payment/wire_transfer_provider/process',
            'reference': self.reference,
        }

    def _extract_amount_data(self, payment_data):
        if self.provider_code != 'wire_transfer_provider':
            return super()._extract_amount_data(payment_data)
        return None

    def _apply_updates(self, payment_data):
        if self.provider_code != 'wire_transfer_provider':
            return super()._apply_updates(payment_data)
        had_receipt = bool(self.wire_receipt_file)
        self._wire_apply_inputs_from_payment_data(payment_data)
        if self._wire_upload_required() and (not self.wire_reference or not self.wire_receipt_file):
            raise ValidationError(_(
                'Debes adjuntar el comprobante y la referencia antes de confirmar el pago por transferencia.'
            ))
        message = _('Transfer selected. Waiting for accounting validation.')
        self._set_pending(state_message=message)
        if not had_receipt and self.wire_receipt_file:
            self._wire_notify_receipt_uploaded()

    def _wire_apply_inputs_from_payment_data(self, payment_data):
        self.ensure_one()
        wire_reference = (payment_data or {}).get('wire_reference')
        filename = (payment_data or {}).get('wire_receipt_filename')
        mimetype = (payment_data or {}).get('wire_receipt_mimetype')
        encoded_content = (payment_data or {}).get('wire_receipt_content')
        content = False
        if encoded_content:
            try:
                content = base64.b64decode(encoded_content, validate=True)
            except (ValueError, TypeError, binascii.Error) as err:
                raise ValidationError(_('El archivo del comprobante no es valido.')) from err
        if wire_reference is None and not content:
            return
        self._wire_apply_customer_inputs(
            wire_reference=wire_reference,
            filename=filename,
            mimetype=mimetype,
            content=content,
        )

    def _wire_get_receipt_upload_error(self):
        self.ensure_one()
        if self.provider_code != 'wire_transfer_provider':
            return _('Esta transaccion no usa transferencia bancaria.')
        if self.state not in ('draft', 'pending'):
            return _('Esta transaccion ya no permite cargar comprobantes.')
        return False

    def _wire_upload_required(self):
        self.ensure_one()
        return self.provider_code == 'wire_transfer_provider'

    def _wire_validate_reference(self, wire_reference):
        self.ensure_one()
        value = (wire_reference or '').strip()
        if self._wire_upload_required() and not value:
            raise ValidationError(_('La referencia del comprobante es obligatoria.'))
        return value

    def _wire_validate_receipt_file(self, filename, mimetype, content):
        self.ensure_one()
        if not self._wire_upload_required() and not content:
            return False

        if not content:
            raise ValidationError(_('Debes adjuntar un comprobante para continuar.'))

        max_size_mb = self.provider_id.sudo().wire_receipt_max_size_mb or 2
        max_size = max_size_mb * 1024 * 1024
        if len(content) > max_size:
            raise ValidationError(
                _('El archivo supera el tamano maximo de %(size)s MB.', size=max_size_mb)
            )

        normalized_name = (filename or '').lower()
        if not normalized_name.endswith(('.pdf', '.png', '.jpg', '.jpeg')):
            raise ValidationError(_('Solo se permiten archivos PDF, PNG, JPG o JPEG.'))

        if normalized_name.endswith('.pdf'):
            if not content.startswith(b'%PDF-'):
                raise ValidationError(_('El archivo cargado no es un PDF valido.'))
            return 'application/pdf'

        image_mimetype = self._wire_detect_image_mimetype(content)
        if not image_mimetype:
            raise ValidationError(_('El archivo cargado no es una imagen valida.'))
        return image_mimetype

    def _wire_apply_customer_inputs(self, wire_reference=None, filename=None, mimetype=None, content=None):
        self.ensure_one()
        values = {'wire_reference': self._wire_validate_reference(wire_reference or self.wire_reference)}
        validated_mimetype = self._wire_validate_receipt_file(filename, mimetype, content)
        if content:
            values.update({
                'wire_receipt_file': base64.b64encode(content),
                'wire_receipt_filename': self._wire_sanitize_filename(filename),
                'wire_receipt_mimetype': validated_mimetype,
            })
        self.sudo().write(values)

    def _wire_notify_receipt_uploaded(self):
        """Notifica al cliente que su comprobante esta en proceso de verificacion.

        Reutiliza la plantilla de confirmacion de venta de Odoo sin confirmar el
        pedido: como la transaccion queda en estado 'pending', la plantilla
        renderiza el texto de pago pendiente en lugar del de confirmacion.
        """
        self.ensure_one()
        template = self.env.ref('sale.mail_template_sale_confirmation', raise_if_not_found=False)
        if not template:
            return
        for order in self.sudo().sale_order_ids:
            try:
                order._send_order_notification_mail(template)
            except Exception:
                _logger.exception(
                    'No se pudo enviar la notificacion de comprobante para el pedido %s.',
                    order.name,
                )

    @staticmethod
    def _wire_sanitize_filename(filename):
        cleaned = (
            (filename or 'comprobante')
            .strip()
            .replace('\\', '_')
            .replace('/', '_')
            .replace('"', '_')
            .replace('\r', '_')
            .replace('\n', '_')
        )
        if len(cleaned) > 128:
            name, dot, ext = cleaned.rpartition('.')
            if dot and ext:
                cleaned = f"{name[:100]}.{ext[:20]}"
            else:
                cleaned = cleaned[:128]
        return cleaned or 'comprobante'
