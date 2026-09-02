from dateutil.relativedelta import relativedelta

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.fields import Command


class ReferralCommissionSettlement(models.Model):
    _name = 'referral.commission.settlement'
    _description = "Liquidacion de comisiones de referido"
    _order = 'date_to desc, id desc'

    def _default_date_from(self):
        first_this = fields.Date.context_today(self).replace(day=1)
        return first_this - relativedelta(months=1)

    def _default_date_to(self):
        first_this = fields.Date.context_today(self).replace(day=1)
        return first_this - relativedelta(days=1)

    name = fields.Char(compute='_compute_name', store=True)
    partner_id = fields.Many2one(
        comodel_name='res.partner', string="Partner", required=True,
        domain="[('is_referral_partner', '=', True)]")
    company_id = fields.Many2one(
        'res.company', string="Compañia", default=lambda self: self.env.company)
    currency_id = fields.Many2one(
        'res.currency', compute='_compute_currency_id', store=True)
    date_from = fields.Date(string="Desde", required=True, default=_default_date_from)
    date_to = fields.Date(string="Hasta", required=True, default=_default_date_to)
    payment_due_date = fields.Date(
        string="Vence", compute='_compute_payment_due_date', store=True,
        help="Dia 15 del mes siguiente al periodo (Clausula 9 del contrato).")
    line_ids = fields.One2many(
        'referral.commission', 'settlement_id', string="Comisiones")
    amount_total = fields.Monetary(
        string="Total", compute='_compute_amount_total', store=True,
        currency_field='currency_id')
    vendor_bill_id = fields.Many2one('account.move', string="Factura de proveedor", copy=False)
    state = fields.Selection(
        selection=[('draft', "Borrador"), ('billed', "Facturada"), ('paid', "Pagada")],
        string="Estado", default='draft', required=True)

    @api.depends('partner_id', 'date_to')
    def _compute_name(self):
        for s in self:
            s.name = "Liquidacion %s - %s" % (s.partner_id.name or '', s.date_to or '')

    @api.depends('company_id')
    def _compute_currency_id(self):
        for s in self:
            s.currency_id = (s.company_id or self.env.company).currency_id

    @api.depends('date_to')
    def _compute_payment_due_date(self):
        for s in self:
            s.payment_due_date = (
                (s.date_to + relativedelta(months=1)).replace(day=15)
                if s.date_to else False)

    @api.depends('line_ids.commission_amount')
    def _compute_amount_total(self):
        for s in self:
            s.amount_total = sum(s.line_ids.mapped('commission_amount'))

    def action_generate(self):
        self.ensure_one()
        if self.state != 'draft':
            raise UserError(self.env._("Solo se puede recalcular en borrador."))
        domain = [
            ('partner_id', '=', self.partner_id.id),
            ('state', '=', 'draft'),
            ('settlement_id', '=', False),
            ('date', '>=', self.date_from),
            ('date', '<=', self.date_to),
        ]
        if self.company_id:
            domain.append(('company_id', '=', self.company_id.id))
        commissions = self.env['referral.commission'].search(domain)
        commissions.write({'settlement_id': self.id, 'state': 'settled'})
        return True

    def action_create_vendor_bill(self):
        self.ensure_one()
        if self.vendor_bill_id:
            raise UserError(self.env._("Esta liquidacion ya tiene factura de proveedor."))
        if not self.line_ids:
            raise UserError(self.env._("No hay comisiones en la liquidacion. Pulsa 'Recalcular'."))
        product = self.partner_id.referral_commission_plan_id.commission_product_id
        if not product:
            raise UserError(self.env._(
                "Configura el 'Producto de comision' en el plan del partner %s.",
                self.partner_id.display_name))
        move = self.env['account.move'].create({
            'move_type': 'in_invoice',
            'partner_id': self.partner_id.id,
            'invoice_date': fields.Date.context_today(self),
            'invoice_date_due': self.payment_due_date,
            'company_id': (self.company_id or self.env.company).id,
            'invoice_line_ids': [Command.create({
                'product_id': product.id,
                'name': self.env._(
                    "Comisiones de referidos (%(desde)s a %(hasta)s)",
                    desde=self.date_from, hasta=self.date_to),
                'quantity': 1,
                'price_unit': self.amount_total,
                'tax_ids': [Command.clear()],
            })],
        })
        self.vendor_bill_id = move
        self.state = 'billed'
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'res_id': move.id,
            'view_mode': 'form',
        }

    def action_open_vendor_bill(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.move',
            'res_id': self.vendor_bill_id.id,
            'view_mode': 'form',
        }

    def action_mark_paid(self):
        self.ensure_one()
        self.line_ids.write({'state': 'paid'})
        self.state = 'paid'

    def action_reset_to_draft(self):
        self.ensure_one()
        self.line_ids.write({'state': 'draft', 'settlement_id': False})
        self.state = 'draft'
