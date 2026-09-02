from odoo import api, fields, models


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    sci_template_line_id = fields.Many2one(
        comodel_name='sale.order.template.line',
        string="Linea de plantilla origen",
        ondelete='set null',
        copy=False)

    @api.depends('product_id', 'product_uom_id', 'product_uom_qty')
    def _compute_price_unit(self):
        # El precio definido en la plantilla manda sobre el precio del producto /
        # tarifa (decision "precio fijo"), incluido el 0 (servicio incluido gratis),
        # que el computo nativo descartaria. Se usa la linea de plantilla exacta
        # de origen para evitar ambiguedades cuando un producto se repite.
        super()._compute_price_unit()
        for line in self:
            if line.display_type or not line.sci_template_line_id:
                continue
            line.price_unit = line.sci_template_line_id.price_unit
