from odoo import api, models


class MergePartnerAutomatic(models.TransientModel):
    _inherit = 'base.partner.merge.automatic.wizard'

    @api.model
    def _update_values(self, src_partners, dst_partner):
        # Salvaguarda de fusion para el codigo de Partner:
        # el nativo escribe en el destino el codigo de una fuente que aun existe,
        # lo que violaria unique(referral_code). Se libera el codigo de las fuentes
        # antes de copiarlo y se garantiza que el superviviente quede como Partner
        # con un codigo valido.
        partners = src_partners + dst_partner
        referral_partners = partners.filtered('is_referral_partner')
        keep_code = dst_partner.referral_code or (
            referral_partners[:1].referral_code if referral_partners else False)

        src_codes = src_partners.filtered('referral_code')
        if src_codes:
            src_codes.write({'referral_code': False})

        super()._update_values(src_partners, dst_partner)

        vals = {}
        if referral_partners and not dst_partner.is_referral_partner:
            vals['is_referral_partner'] = True
        if (vals.get('is_referral_partner') or dst_partner.is_referral_partner) \
                and not dst_partner.referral_code:
            vals['referral_code'] = keep_code or dst_partner._sci_generate_referral_code()
        if vals:
            dst_partner.write(vals)
