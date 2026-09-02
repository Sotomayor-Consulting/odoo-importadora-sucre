from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class CommissionManualAdjustment(models.Model):
    _name = 'commission.manual.adjustment'
    _description = 'Ajuste manual de comision'
    _order = 'date desc, id desc'

    sheet_id = fields.Many2one(
        'commission.sheet',
        string='Hoja',
        required=True,
        ondelete='cascade',
        index=True,
    )
    sheet_state = fields.Selection(
        related='sheet_id.state',
        store=True,
        readonly=True,
    )

    employee_id = fields.Many2one(
        'hr.employee',
        string='Empleado',
        required=True,
        index=True,
    )
    team_id = fields.Many2one(
        'crm.team',
        string='Equipo',
        help='Opcional. Asigna el ajuste al neto del empleado en ese equipo.',
    )
    company_id = fields.Many2one(
        'res.company',
        string='Compania',
        required=True,
        default=lambda self: self.env.company,
    )
    currency_id = fields.Many2one(
        'res.currency',
        related='company_id.currency_id',
        readonly=True,
    )

    reason = fields.Selection(
        [
            ('trustpilot', 'Trust Pilot'),
            ('correction', 'Correccion'),
            ('bonus', 'Bono'),
            ('other', 'Otro'),
        ],
        default='other',
        required=True,
    )
    date = fields.Date(
        string='Fecha',
        required=True,
        default=fields.Date.context_today,
    )
    description = fields.Char(required=True)

    # ------------------------------------------------------------------
    # Modo: importe fijo o tasa porcentual
    # ------------------------------------------------------------------
    adjustment_mode = fields.Selection(
        [
            ('fixed', 'Importe $'),
            ('percentage', 'Tasa %'),
        ],
        string='Modo',
        default='fixed',
        required=True,
    )
    amount = fields.Monetary(
        string='Monto',
        help='Usado en modo "Importe $". Puede ser negativo (correccion).',
    )
    rate = fields.Float(
        string='Tasa (%)',
        digits=(5, 2),
        help='Usado en modo "Tasa %". Se aplica sobre la base de referencia.',
    )
    base_reference = fields.Selection(
        [
            ('commission', 'Comision bruta del empleado en la hoja'),
            ('net', 'Neto del empleado en la hoja'),
        ],
        string='Base del %',
        default='commission',
        help='Solo aplica en modo Tasa %. Define sobre que monto se calcula el %.',
    )
    computed_amount = fields.Monetary(
        string='Importe calculado',
        compute='_compute_computed_amount',
        store=True,
        help='Monto efectivo del ajuste tras evaluar modo y base. Es lo que se suma al neto.',
    )

    notes = fields.Text(string='Notas')

    # ------------------------------------------------------------------
    # Computed
    # ------------------------------------------------------------------
    @api.depends(
        'adjustment_mode', 'amount', 'rate', 'base_reference',
        'employee_id', 'team_id', 'sheet_id', 'sheet_id.line_ids',
        'sheet_id.line_ids.commission_amount', 'sheet_id.line_ids.net_amount',
    )
    def _compute_computed_amount(self):
        for adj in self:
            if adj.adjustment_mode == 'fixed':
                adj.computed_amount = adj.amount or 0.0
                continue
            # Modo porcentaje: calcular sobre la base de referencia.
            domain = [
                ('sheet_id', '=', adj.sheet_id.id),
                ('employee_id', '=', adj.employee_id.id),
                ('source', '=', 'team'),
            ]
            if adj.team_id:
                domain.append(('team_id', '=', adj.team_id.id))
            lines = adj.env['commission.line'].search(domain)
            if adj.base_reference == 'net':
                base = sum(lines.mapped('net_amount'))
            else:
                base = sum(lines.mapped('commission_amount'))
            adj.computed_amount = base * (adj.rate / 100.0)

    # ------------------------------------------------------------------
    # Constraints
    # ------------------------------------------------------------------
    @api.constrains('adjustment_mode', 'amount', 'rate')
    def _check_amount_or_rate(self):
        for adj in self:
            if adj.adjustment_mode == 'fixed' and adj.amount == 0:
                raise ValidationError(_(
                    'En modo "Importe $" el monto no puede ser cero.'
                ))
            if adj.adjustment_mode == 'percentage' and adj.rate <= 0:
                raise ValidationError(_(
                    'En modo "Tasa %" la tasa debe ser mayor a cero.'
                ))
