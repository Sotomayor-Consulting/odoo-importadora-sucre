from odoo import api, fields, models


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    referrer_id = fields.Many2one(
        comodel_name='res.partner',
        string="Referido por",
        domain="[('is_referral_partner', '=', True)]",
        compute='_compute_referrer_id',
        store=True, readonly=False,
        help="Partner que se lleva la comision de esta venta. Se hereda del"
             " cliente y puede ajustarse por orden.")
    referral_code_entry = fields.Char(string="Codigo de referido")

    @api.depends('partner_id')
    def _compute_referrer_id(self):
        for order in self:
            if order.partner_id.referrer_partner_id:
                order.referrer_id = order.partner_id.referrer_partner_id

    @api.onchange('referral_code_entry')
    def _onchange_referral_code_entry(self):
        if not self.referral_code_entry:
            return
        partner = self.env['res.partner']._sci_partner_by_referral_code(
            self.referral_code_entry)
        if not partner:
            return {'warning': {
                'title': "Codigo no valido",
                'message': "No existe un Partner con el codigo %s." % self.referral_code_entry,
            }}
        self.referrer_id = partner

    def _prepare_invoice(self):
        vals = super()._prepare_invoice()
        if self.referrer_id:
            vals['referral_referrer_id'] = self.referrer_id.id
        return vals
