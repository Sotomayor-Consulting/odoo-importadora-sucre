from odoo import fields, models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    sci_task_user_id = fields.Many2one(
        comodel_name='res.users',
        string="Responsable de tarea",
        domain="[('share', '=', False)]",
        help="Persona asignada a la tarea generada por este servicio."
             " Si se deja vacio, se hereda de la categoria.")
    sci_task_role_id = fields.Many2one(
        comodel_name='project.role',
        string="Rol de tarea",
        help="Rol cuya persona a cargo se asigna a la tarea (alternativa"
             " reutilizable al responsable directo).")
    sci_estimated_hours = fields.Float(
        string="Tiempo estimado (h)",
        help="Tiempo asignado a la tarea, por unidad vendida. Si es 0 se hereda"
             " de la categoria.")
    sci_deadline_days = fields.Integer(
        string="Plazo (dias)",
        help="Dias desde la confirmacion de la orden hasta la fecha limite de la"
             " tarea. Si es 0 se hereda de la categoria.")

    def _sci_get_task_assignment(self):
        """Resuelve responsable / horas / plazo.

        Precedencia (gana el mas especifico): el servicio prevalece sobre la
        categoria; dentro de cada nivel, la persona directa prevalece sobre la
        persona del rol.

        :return: dict con claves ``user`` (res.users), ``role`` (project.role),
            ``hours`` (float) y ``deadline_days`` (int).
        """
        self.ensure_one()
        categ = self.categ_id
        user = self.env['res.users']
        role = self.env['project.role']
        if self.sci_task_user_id:
            user = self.sci_task_user_id
            role = self.sci_task_role_id
        elif self.sci_task_role_id.sci_user_id:
            user = self.sci_task_role_id.sci_user_id
            role = self.sci_task_role_id
        elif categ.sci_task_user_id:
            user = categ.sci_task_user_id
            role = categ.sci_task_role_id
        elif categ.sci_task_role_id.sci_user_id:
            user = categ.sci_task_role_id.sci_user_id
            role = categ.sci_task_role_id
        return {
            'user': user,
            'role': role,
            'hours': self.sci_estimated_hours or categ.sci_estimated_hours,
            'deadline_days': self.sci_deadline_days or categ.sci_deadline_days,
        }
