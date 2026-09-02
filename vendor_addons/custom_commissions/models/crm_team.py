from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class CrmTeam(models.Model):
    _inherit = 'crm.team'

    commission_active = fields.Boolean(
        string='Activo en comisiones',
        default=False,
        help='Si esta marcado, el equipo entra en el calculo de las hojas de comision.',
    )

    # ------------------------------------------------------------------
    # Defaults (catch-all si ninguna regla matchea).
    # El "que" (rule_type, frequency, amount_basis) vive en commission.rate.rule.
    # ------------------------------------------------------------------
    commission_computation = fields.Selection(
        [
            ('percentage', 'Porcentaje'),
            ('fixed', 'Monto fijo'),
        ],
        string='Tipo de tasa por defecto',
        default='percentage',
        required=True,
    )
    commission_rate = fields.Float(
        string='Tasa por defecto (%)',
        digits=(5, 2),
        help='Catch-all aplicado cuando no hay regla especifica que matchee.',
    )
    commission_fixed_amount = fields.Monetary(
        string='Monto fijo por defecto',
        currency_field='currency_id',
    )
    commission_base_salary_deduction = fields.Monetary(
        string='Descuento sueldo base',
        currency_field='currency_id',
        help=(
            'Monto fijo que se resta del total mensual del empleado antes de pagar. '
            'Para Ventas tipicamente USD 800.'
        ),
    )
    commission_split_method = fields.Selection(
        [
            ('seller', 'Vendedor de la orden'),
            ('equal', 'Reparto igual entre miembros'),
            ('task_assignee', 'Asignados de la tarea'),
        ],
        string='Reparto',
        default='seller',
        help='Como se determina el empleado que cobra cada linea.',
    )

    commission_rate_rule_ids = fields.One2many(
        'commission.rate.rule',
        'team_id',
        string='Reglas de comision',
    )
    commission_rate_rule_count = fields.Integer(
        compute='_compute_commission_rate_rule_count',
    )

    @api.depends('commission_rate_rule_ids')
    def _compute_commission_rate_rule_count(self):
        for team in self:
            team.commission_rate_rule_count = len(team.commission_rate_rule_ids)

    @api.constrains('commission_rate', 'commission_fixed_amount')
    def _check_default_amounts(self):
        for team in self:
            if team.commission_rate < 0:
                raise ValidationError(_('La tasa por defecto no puede ser negativa.'))
            if team.commission_fixed_amount < 0:
                raise ValidationError(_('El monto fijo por defecto no puede ser negativo.'))

    def get_default_commission(self, base_amount, quantity=None):
        """Aplica la tasa por defecto del equipo a una base."""
        self.ensure_one()
        if self.commission_computation == 'fixed':
            if quantity is not None:
                return self.commission_fixed_amount * quantity
            return self.commission_fixed_amount
        return base_amount * (self.commission_rate / 100.0)

    def action_open_rate_rules(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Reglas de comision - %s') % self.name,
            'res_model': 'commission.rate.rule',
            'view_mode': 'list,form',
            'domain': [('team_id', '=', self.id)],
            'context': {'default_team_id': self.id},
        }
