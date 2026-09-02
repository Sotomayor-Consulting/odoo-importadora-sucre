from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class PaymentProvider(models.Model):
    _inherit = 'payment.provider'

    code = fields.Selection(
        selection_add=[
            ('wire_transfer_provider', 'Transferencia bancaria'),
        ],
        ondelete={
            'wire_transfer_provider': 'set default',
        },
    )
    wire_allow_receipt_upload = fields.Boolean(
        string='Subir comprobante',
        default=True,
    )
    wire_receipt_max_size_mb = fields.Integer(
        string='Tamano maximo del comprobante (MB)',
        default=2,
    )
    wire_company_partner_id = fields.Many2one(
        'res.partner',
        related='company_id.partner_id',
        readonly=True,
    )
    wire_company_bank_id = fields.Many2one(
        'res.partner.bank',
        string='Cuenta bancaria de la compania',
        domain="[('partner_id', '=', wire_company_partner_id)]",
        help='Selecciona una cuenta bancaria de la compania para mostrarla en el checkout.',
    )
    wire_company_bank_holder = fields.Char(
        related='wire_company_bank_id.acc_holder_name',
        string='Beneficiario',
        readonly=False,
    )
    wire_company_bank_vat = fields.Char(
        related='wire_company_bank_id.wire_beneficiary_vat',
        string='Numero de identificacion',
        readonly=False,
    )
    _wire_receipt_size_positive = models.Constraint(
        'CHECK(wire_receipt_max_size_mb > 0)',
        'El tamano maximo del comprobante debe ser mayor a cero.',
    )

    def _get_default_payment_method_codes(self):
        self.ensure_one()
        if self.code != 'wire_transfer_provider':
            return super()._get_default_payment_method_codes()
        return {'bank_transfer'}

    @api.model
    def _get_removal_values(self):
        values = super()._get_removal_values()
        values.update({
            'wire_allow_receipt_upload': False,
            'wire_receipt_max_size_mb': 2,
            'wire_company_bank_id': False,
        })
        return values

    def _wire_get_default_pending_msg(self):
        self.ensure_one()
        return _(
            'Hemos recibido tu solicitud de pago por transferencia bancaria. '
            'Tu orden quedara pendiente hasta validar el pago.'
        )

    @api.model
    def _wire_ensure_pending_message(self, provider_ids):
        providers = self.browse(provider_ids).filtered(
            lambda provider: provider.code == 'wire_transfer_provider'
        )
        for provider in providers:
            if not provider.pending_msg:
                provider.pending_msg = provider._wire_get_default_pending_msg()

    @api.constrains('wire_company_bank_id', 'company_id')
    def _check_wire_company_bank_id(self):
        for provider in self:
            if not provider.wire_company_bank_id or not provider.company_id.partner_id:
                continue
            if provider.wire_company_bank_id.partner_id != provider.company_id.partner_id:
                raise ValidationError(_(
                    'La cuenta bancaria seleccionada debe pertenecer al partner de la compania.'
                ))
