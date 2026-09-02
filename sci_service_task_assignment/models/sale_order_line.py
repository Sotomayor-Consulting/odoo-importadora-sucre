from datetime import timedelta

from odoo import fields, models
from odoo.fields import Command


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    def _convert_qty_company_hours(self, dest_company):
        # Alimenta el "Tiempo asignado" de la tarea desde el estimado configurado
        # (los servicios se venden en Unidades, no en horas). Sobreescribir este
        # metodo nativo hace que el valor sea consistente tanto al crear la tarea
        # (con o sin plantilla de proyecto) como al cambiar la cantidad vendida.
        hours = super()._convert_qty_company_hours(dest_company)
        if self.product_id:
            cfg = self.product_id.product_tmpl_id._sci_get_task_assignment()
            if cfg['hours']:
                return cfg['hours'] * self.product_uom_qty
        return hours

    def _timesheet_create_task(self, project):
        # Tras crear la tarea (por la ruta que sea: con o sin plantilla), se
        # inyectan responsable, rol y fecha limite segun la configuracion del
        # servicio/categoria. La config prevalece sobre lo que ponga la plantilla.
        task = super()._timesheet_create_task(project)
        if not self.product_id:
            return task
        cfg = self.product_id.product_tmpl_id._sci_get_task_assignment()
        updates = {}
        if cfg['user']:
            updates['user_ids'] = [Command.set(cfg['user'].ids)]
        if cfg['role']:
            updates['role_ids'] = [Command.link(cfg['role'].id)]
        if cfg['deadline_days']:
            base = self.order_id.date_order or fields.Datetime.now()
            updates['date_deadline'] = base + timedelta(days=cfg['deadline_days'])
        if updates:
            task.sudo().write(updates)
        return task
