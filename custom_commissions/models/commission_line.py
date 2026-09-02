from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class CommissionLine(models.Model):
    _name = 'commission.line'
    _description = 'Linea de comision por empleado'
    _order = 'sheet_id desc, team_id, employee_id'

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
    date_from = fields.Date(related='sheet_id.date_from', store=True)
    date_to = fields.Date(related='sheet_id.date_to', store=True)

    team_id = fields.Many2one(
        'crm.team',
        string='Equipo',
        index=True,
        ondelete='restrict',
        help='Vacio para lineas de roles por producto o ajustes manuales sin equipo.',
    )
    source = fields.Selection(
        [
            ('team', 'Equipo CRM'),
            ('product_role', 'Rol por producto'),
            ('manual', 'Ajuste manual'),
        ],
        default='team',
        required=True,
        index=True,
    )

    employee_id = fields.Many2one(
        'hr.employee',
        string='Empleado',
        required=True,
        index=True,
        ondelete='restrict',
    )
    user_id = fields.Many2one(
        'res.users',
        related='employee_id.user_id',
        store=True,
        index=True,
        readonly=True,
        help='Usuario asociado, almacenado para record rules.',
    )

    company_id = fields.Many2one(
        'res.company',
        string='Compania',
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )
    currency_id = fields.Many2one(
        'res.currency',
        related='company_id.currency_id',
        store=True,
        readonly=True,
    )

    # Bases auditables — se computan desde las lineas de detalle al recalcular.
    base_revenue = fields.Monetary(
        string='Ingreso',
        compute='_compute_bases',
        store=True,
        help='Suma del valor de venta (pre-impuesto) que cae en el periodo.',
    )
    base_cost = fields.Monetary(
        string='Costo proveedor',
        compute='_compute_bases',
        store=True,
        help='Suma de cost_amount de los detail lines (standard_price o analytic).',
    )
    base_margin = fields.Monetary(
        string='Margen',
        compute='_compute_base_margin',
        store=True,
    )
    base_amount = fields.Monetary(
        string='Base aplicada',
        compute='_compute_bases',
        store=True,
        help='Monto efectivamente usado como base para calcular la comision (revenue o margin segun la regla).',
    )

    commission_amount = fields.Monetary(
        string='Comision bruta',
        compute='_compute_commission_amount',
        store=True,
    )
    base_salary_deduction = fields.Monetary(
        string='Descuento sueldo base',
        default=0.0,
    )
    net_amount = fields.Monetary(
        string='Neto',
        compute='_compute_net_amount',
        store=True,
    )

    detail_line_ids = fields.One2many(
        'commission.detail.line',
        'line_id',
        string='Lineas de detalle',
    )
    detail_count = fields.Integer(compute='_compute_detail_count')

    notes = fields.Char()

    # ------------------------------------------------------------------
    # Computed
    # ------------------------------------------------------------------
    @api.depends('detail_line_ids.base_amount', 'detail_line_ids.cost_amount')
    def _compute_bases(self):
        for line in self:
            base_amount = sum(line.detail_line_ids.mapped('base_amount'))
            line.base_amount = base_amount
            line.base_revenue = base_amount
            line.base_cost = sum(line.detail_line_ids.mapped('cost_amount'))

    @api.depends('base_revenue', 'base_cost')
    def _compute_base_margin(self):
        for line in self:
            line.base_margin = (line.base_revenue or 0.0) - (line.base_cost or 0.0)

    @api.depends('detail_line_ids.commission_amount')
    def _compute_commission_amount(self):
        for line in self:
            line.commission_amount = sum(line.detail_line_ids.mapped('commission_amount'))

    @api.depends('commission_amount', 'base_salary_deduction', 'source')
    def _compute_net_amount(self):
        for line in self:
            if line.source == 'team':
                line.net_amount = max(0.0, line.commission_amount - (line.base_salary_deduction or 0.0))
            else:
                # product_role y manual no descuentan sueldo base.
                line.net_amount = line.commission_amount

    def _compute_detail_count(self):
        for line in self:
            line.detail_count = len(line.detail_line_ids)

    # ------------------------------------------------------------------
    # Constraints
    # ------------------------------------------------------------------
    @api.constrains('sheet_id', 'employee_id', 'team_id', 'source')
    def _check_unique_line(self):
        for line in self:
            domain = [
                ('id', '!=', line.id),
                ('sheet_id', '=', line.sheet_id.id),
                ('employee_id', '=', line.employee_id.id),
                ('source', '=', line.source),
                ('team_id', '=', line.team_id.id or False),
            ]
            if line.search_count(domain, limit=1):
                raise ValidationError(_(
                    'Ya existe una linea para %(employee)s en %(sheet)s '
                    'con equipo "%(team)s" y fuente "%(source)s".'
                ) % {
                    'employee': line.employee_id.display_name,
                    'sheet': line.sheet_id.name,
                    'team': line.team_id.name or _('(sin equipo)'),
                    'source': dict(line._fields['source']._description_selection(self.env))[line.source],
                })

    @api.constrains('base_salary_deduction')
    def _check_deduction(self):
        for line in self:
            if line.base_salary_deduction < 0:
                raise ValidationError(_('El descuento no puede ser negativo.'))

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------
    def action_open_detail_lines(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Detalle - %s') % self.employee_id.display_name,
            'res_model': 'commission.detail.line',
            'view_mode': 'list,form',
            'domain': [('line_id', '=', self.id)],
        }
