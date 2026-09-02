import secrets

from odoo import api, fields, models

# Longitud por defecto del codigo de Partner (minimo 6).
REFERRAL_CODE_LENGTH = 10


class ResPartner(models.Model):
    _inherit = 'res.partner'

    is_referral_partner = fields.Boolean(
        string="Es Partner referido",
        help="Marca al contacto como Partner del programa de referidos.")
    referral_code = fields.Char(
        string="Codigo de Partner",
        readonly=True,
        copy=False,
        index=True,
        help="Codigo unico, personal e intransferible asignado al Partner.")
    referral_agreement_date = fields.Date(
        string="Fecha del acuerdo",
        help="Fecha de firma del Acuerdo de Colaboracion y Referidos.")

    referral_partner_contract = fields.Binary(string='Contrato de partner')
    referral_partner_contract_file_name = fields.Char(string='Nombre del archivo')
    referral_contract_end_date = fields.Date(
        string="Fin del contrato",
        help="Fecha de finalizacion del contrato del Partner.")
    referral_commission_plan_id = fields.Many2one(
        comodel_name='referral.commission.plan',
        string="Plan de comision",
        help="Plan de tasas aplicado a las ventas de los clientes que refiere.")

    # === Como cliente referido ===
    referrer_partner_id = fields.Many2one(
        comodel_name='res.partner',
        string="Referido por",
        domain="[('is_referral_partner', '=', True)]",
        index=True,
        help="Partner del programa que trajo a este cliente.")
    referral_validated = fields.Boolean(
        string="Referido validado",
        help="SCI confirma que el referido es legitimo; habilita el calculo de"
             " comision.")
    referral_code_entry = fields.Char(
        string="Codigo de referido",
        help="Escribe el codigo del Partner para vincular este contacto a el.")
    referred_partner_ids = fields.One2many(
        comodel_name='res.partner',
        inverse_name='referrer_partner_id',
        string="Clientes referidos")
    referred_partner_count = fields.Integer(
        compute='_compute_referred_partner_count')

    _referral_code_unique = models.Constraint(
        'unique(referral_code)',
        "El codigo de Partner referido debe ser unico.")

    @api.model_create_multi
    def create(self, vals_list):
        plan = self._sci_default_commission_plan()
        for vals in vals_list:
            if vals.get('is_referral_partner'):
                if not vals.get('referral_code'):
                    vals['referral_code'] = self._sci_generate_referral_code()
                if plan and not vals.get('referral_commission_plan_id'):
                    vals['referral_commission_plan_id'] = plan.id
        return super().create(vals_list)

    def write(self, vals):
        res = super().write(vals)
        if vals.get('is_referral_partner'):
            plan = self._sci_default_commission_plan()
            for partner in self:
                if not partner.referral_code:
                    partner.referral_code = self._sci_generate_referral_code()
                if plan and not partner.referral_commission_plan_id:
                    partner.referral_commission_plan_id = plan
        return res

    @api.model
    def _sci_default_commission_plan(self):
        return self.env.ref(
            'sci_referral_partner.plan_program', raise_if_not_found=False)

    @api.model
    def _sci_generate_referral_code(self, length=None):
        """Genera un codigo aleatorio unico en hex mayusculas.

        Equivalente a `upper(substr(encode(gen_random_bytes(...), 'hex'), 1, len))`:
        toma bytes aleatorios seguros, los pasa a hex, recorta a `length` y reintenta
        si ya existe.
        """
        length = max(6, length or REFERRAL_CODE_LENGTH)
        nbytes = (length + 1) // 2  # ceil(length / 2)
        while True:
            candidate = secrets.token_hex(nbytes)[:length].upper()
            if not self.sudo().search_count([('referral_code', '=', candidate)]):
                return candidate

    @api.depends('referred_partner_ids')
    def _compute_referred_partner_count(self):
        for partner in self:
            partner.referred_partner_count = len(partner.referred_partner_ids)

    @api.model
    def _sci_partner_by_referral_code(self, code):
        """Devuelve el Partner cuyo codigo coincide (insensible a may/min)."""
        code = (code or '').strip().upper()
        if not code:
            return self.browse()
        return self.search([
            ('is_referral_partner', '=', True),
            ('referral_code', '=', code),
        ], limit=1)

    @api.onchange('referral_code_entry')
    def _onchange_referral_code_entry(self):
        if not self.referral_code_entry:
            return
        partner = self._sci_partner_by_referral_code(self.referral_code_entry)
        if not partner:
            return {'warning': {
                'title': "Codigo no valido",
                'message': "No existe un Partner con el codigo %s." % self.referral_code_entry,
            }}
        self.referrer_partner_id = partner

    def action_view_referred_partners(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': "Clientes referidos",
            'res_model': 'res.partner',
            'view_mode': 'list,form',
            'domain': [('referrer_partner_id', '=', self.id)],
            'context': {'default_referrer_partner_id': self.id},
        }
