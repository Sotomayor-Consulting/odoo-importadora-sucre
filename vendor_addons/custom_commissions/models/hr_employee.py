from odoo import fields, models


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    commission_currency_id = fields.Many2one(
        'res.currency',
        string='Moneda de comision',
        related='company_id.currency_id',
        readonly=True,
    )
    commission_base_salary = fields.Monetary(
        string='Sueldo base de comision (override)',
        currency_field='commission_currency_id',
        default=0.0,
        groups='hr.group_hr_user',
        help=(
            'Si es mayor a 0, sobreescribe el descuento del equipo al calcular '
            'el neto de comision para este empleado. Util cuando un asesor '
            'tiene un sueldo base distinto al estandar del equipo.'
        ),
    )
