from odoo import fields, models


class ProductCategory(models.Model):
    _inherit = 'product.category'

    sci_task_user_id = fields.Many2one(
        comodel_name='res.users',
        string="Responsable de tarea",
        domain="[('share', '=', False)]",
        help="Responsable por defecto para los servicios de esta categoria.")
    sci_task_role_id = fields.Many2one(
        comodel_name='project.role',
        string="Rol de tarea")
    sci_estimated_hours = fields.Float(
        string="Tiempo estimado (h)")
    sci_deadline_days = fields.Integer(
        string="Plazo (dias)")
