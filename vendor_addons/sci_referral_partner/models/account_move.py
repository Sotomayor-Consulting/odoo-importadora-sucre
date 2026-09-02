from odoo import api, fields, models
from odoo.exceptions import UserError


class AccountMove(models.Model):
    _inherit = 'account.move'

    referral_referrer_id = fields.Many2one(
        comodel_name='res.partner',
        string="Referido por",
        domain="[('is_referral_partner', '=', True)]",
        compute='_compute_referral_referrer_id',
        store=True, readonly=False,
        help="Partner que se lleva la comision de esta factura.")
    referral_commission_generated = fields.Boolean(
        string="Comision generada", copy=False, default=False)

    @api.depends('partner_id')
    def _compute_referral_referrer_id(self):
        for move in self:
            if move.move_type in ('out_invoice', 'out_refund'):
                referrer = move.commercial_partner_id.referrer_partner_id
                if referrer:
                    move.referral_referrer_id = referrer

    def _referral_make_commission(self):
        """Genera las comisiones de referido de las facturas cobradas.

        Adaptado del motor de `partner_commission._make_commission`: itera las
        lineas comisionables, resuelve la regla del plan del referidor y crea un
        `referral.commission` por linea (negativo en reembolsos = clawback).
        """
        Commission = self.env['referral.commission'].sudo()
        for move in self.filtered(lambda m: m.move_type in ('out_invoice', 'out_refund')):
            if move.referral_commission_generated or not move.referral_referrer_id:
                continue
            plan = move.referral_referrer_id.referral_commission_plan_id
            if not plan:
                continue
            sign = 1 if move.move_type == 'out_invoice' else -1
            vals_list = []
            for line in move.invoice_line_ids:
                if not line.product_id or line.display_type in (
                        'line_section', 'line_subsection', 'line_note'):
                    continue
                if not line.product_id.referral_commissionable:
                    continue
                rule = plan._match_rules(line.product_id)
                if not rule:
                    continue
                commission = move.currency_id.round(
                    rule._compute_commission(line.price_subtotal))
                if not commission:
                    continue
                vals_list.append({
                    'partner_id': move.referral_referrer_id.id,
                    'customer_id': move.commercial_partner_id.id,
                    'invoice_id': move.id,
                    'invoice_line_id': line.id,
                    'product_id': line.product_id.id,
                    'company_id': move.company_id.id,
                    'currency_id': move.currency_id.id,
                    'date': move.invoice_date or fields.Date.context_today(move),
                    'base_amount': line.price_subtotal * sign,
                    'rate': rule.rate if rule.commission_type == 'percentage' else 0.0,
                    'commission_amount': commission * sign,
                    'is_clawback': sign < 0,
                })
            if vals_list:
                Commission.create(vals_list)
                move.referral_commission_generated = True
                move.message_post(body=self.env._(
                    "Comision de referido generada para %s.",
                    move.referral_referrer_id.display_name))

    def _invoice_paid_hook(self):
        res = super()._invoice_paid_hook()
        self.filtered(
            lambda m: m.move_type == 'out_invoice')._referral_make_commission()
        # Clawback: nota de credito cuya factura original tenia comision.
        self.filtered(
            lambda m: m.move_type == 'out_refund' and m.reversed_entry_id
            and m.reversed_entry_id.referral_commission_generated
        )._referral_make_commission()
        return res

    def _reverse_moves(self, default_values_list=None, cancel=False):
        if not default_values_list:
            default_values_list = [{} for _ in self]
        for move, dv in zip(self, default_values_list):
            dv.setdefault('referral_referrer_id', move.referral_referrer_id.id)
        return super()._reverse_moves(default_values_list, cancel)

    def action_referral_generate_commission(self):
        """Genera la comision manualmente, con diagnostico de por que no se crea."""
        self.ensure_one()
        if self.move_type not in ('out_invoice', 'out_refund'):
            raise UserError(self.env._("Solo aplica a facturas de cliente."))
        if self.referral_commission_generated:
            raise UserError(self.env._("Esta factura ya genero comision."))
        if not self.referral_referrer_id:
            raise UserError(self.env._(
                "La factura no tiene Partner referidor ('Referido por'). Asignalo en"
                " la venta o en la factura."))
        plan = self.referral_referrer_id.referral_commission_plan_id
        if not plan:
            raise UserError(self.env._(
                "El Partner %s no tiene un plan de comision asignado.",
                self.referral_referrer_id.display_name))
        Commission = self.env['referral.commission']
        before = Commission.search_count([('invoice_id', '=', self.id)])
        self._referral_make_commission()
        if Commission.search_count([('invoice_id', '=', self.id)]) > before:
            return True

        # Diagnostico detallado: muestra reglas del plan y, por linea, su categoria
        # y si coincidio, para ver el desajuste exacto.
        plan_rules = "\n".join(
            "  - %s -> %s" % (
                rule.category_id.display_name or rule.product_id.display_name or "?",
                ("%g%%" % rule.rate) if rule.commission_type == 'percentage'
                else ("%g (fijo)" % rule.fixed_amount),
            )
            for rule in plan.rule_ids
        ) or "  (el plan no tiene reglas)"
        lines_info = []
        for line in self.invoice_line_ids:
            if not line.product_id or line.display_type in (
                    'line_section', 'line_subsection', 'line_note'):
                continue
            rule = plan._match_rules(line.product_id)
            lines_info.append("  - %s | categoria: %s | comisionable: %s | regla: %s" % (
                line.product_id.display_name,
                line.product_id.categ_id.display_name,
                "si" if line.product_id.referral_commissionable else "NO",
                ("%g%%" % rule.rate) if rule else "ninguna",
            ))
        raise UserError(self.env._(
            "No se genero comision.\n\nReglas del plan '%(plan)s':\n%(rules)s\n\n"
            "Lineas de la factura:\n%(lines)s",
            plan=plan.name,
            rules=plan_rules,
            lines="\n".join(lines_info) or "  (sin lineas de producto)"))
