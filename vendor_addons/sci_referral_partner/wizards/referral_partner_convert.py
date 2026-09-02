from odoo import fields, models


class ReferralPartnerConvert(models.TransientModel):
    _name = 'sci.referral.partner.convert'
    _description = "Convertir contacto en Partner referido"

    partner_id = fields.Many2one(
        comodel_name='res.partner',
        string="Contacto",
        required=True,
        default=lambda self: self.env.context.get('active_id'))
    referral_agreement_date = fields.Date(
        string="Fecha del acuerdo",
        default=fields.Date.context_today)
    referral_contract_end_date = fields.Date(string="Fin del contrato")
    referral_partner_contract = fields.Binary(string="Contrato de partner")
    referral_partner_contract_file_name = fields.Char(string="Nombre del archivo")

    def action_convert(self):
        self.ensure_one()
        self.partner_id.write({
            'is_referral_partner': True,
            'referral_agreement_date': self.referral_agreement_date,
            'referral_contract_end_date': self.referral_contract_end_date,
            'referral_partner_contract': self.referral_partner_contract,
            'referral_partner_contract_file_name': self.referral_partner_contract_file_name,
        })
        return {'type': 'ir.actions.act_window_close'}
