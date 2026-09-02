from odoo import api, fields, models


class ResPartnerBank(models.Model):
    _inherit = 'res.partner.bank'

    wire_beneficiary_vat = fields.Char(
        string='Numero de identificacion',
        help='Numero de identificacion (cedula, RUC, pasaporte) del titular de la cuenta.',
    )
    wire_account_type = fields.Selection(
        selection=[('savings', 'Ahorros'), ('checking', 'Corriente')],
        string='Tipo de cuenta',
    )

    @api.onchange('partner_id')
    def _onchange_partner_id_wire_defaults(self):
        for bank in self:
            if not bank.partner_id:
                continue
            if not bank.acc_holder_name:
                bank.acc_holder_name = bank.partner_id.name
            if not bank.wire_beneficiary_vat:
                bank.wire_beneficiary_vat = bank.partner_id.vat
