from odoo import fields, models


class ProjectRole(models.Model):
    _inherit = 'project.role'

    sci_user_id = fields.Many2one(
        comodel_name='res.users',
        string="Persona a cargo",
        domain="[('share', '=', False)]",
        help="Persona que se asigna a las tareas cuyo servicio o categoria"
             " utiliza este rol.")
