from odoo import api, fields, models


class SaleOrderTemplateLine(models.Model):
    _inherit = 'sale.order.template.line'

    price_unit = fields.Float(
        string="Precio unitario",
        digits='Product Price',
        compute='_compute_price_unit',
        store=True, readonly=False, precompute=True,
        help="Se completa con el precio de venta del producto al seleccionarlo"
             " y puede editarse. El valor definido aqui se aplica a la orden de"
             " venta al usar la plantilla.")

    # Opciones de seccion replicadas desde sale.order.line (ocultan precios o
    # composicion de las lineas de la seccion en el portal y los reportes).
    collapse_prices = fields.Boolean(
        string="Ocultar precios",
        copy=True,
        default=False)
    collapse_composition = fields.Boolean(
        string="Ocultar composicion",
        copy=True,
        default=False)

    @api.depends('product_id', 'product_uom_id')
    def _compute_price_unit(self):
        for line in self:
            if line.display_type or not line.product_id:
                line.price_unit = 0.0
                continue
            price = line.product_id.lst_price
            product_uom = line.product_id.uom_id
            if line.product_uom_id and product_uom and line.product_uom_id != product_uom:
                price = product_uom._compute_price(price, line.product_uom_id)
            line.price_unit = price

    def _prepare_order_line_values(self):
        vals = super()._prepare_order_line_values()
        if not self.display_type:
            vals['sci_template_line_id'] = self.id
            vals['price_unit'] = self.price_unit
        vals['collapse_prices'] = self.collapse_prices
        vals['collapse_composition'] = self.collapse_composition
        return vals
