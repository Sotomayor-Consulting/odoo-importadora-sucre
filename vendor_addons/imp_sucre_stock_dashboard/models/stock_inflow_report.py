from odoo import fields, models, tools


class StockInflowReport(models.Model):
    """Ingresos de inventario: recepciones de compra y productos terminados.

    stock.report del core no sirve aqui: sus fechas vienen del albaran, que las
    ordenes de produccion no tienen, asi que un filtro de periodo las descarta;
    tampoco distingue el producto terminado de la materia prima consumida.
    """
    _name = 'imp.stock.inflow.report'
    _description = "Ingresos de inventario"
    _auto = False
    _order = 'date desc'

    date = fields.Datetime("Fecha", readonly=True)
    product_id = fields.Many2one('product.product', "Producto", readonly=True)
    categ_id = fields.Many2one('product.category', "Categoria del producto", readonly=True)
    origin_ref = fields.Char("Documento", readonly=True)
    source = fields.Selection(
        [('purchase', 'Compra'),
         ('production', 'Produccion'),
         ('customer_return', 'Devolucion de cliente')],
        string="Origen", readonly=True)
    purchase_order_id = fields.Many2one('purchase.order', "Orden de compra", readonly=True)
    picking_id = fields.Many2one('stock.picking', "Recepcion", readonly=True)
    production_id = fields.Many2one('mrp.production', "Orden de produccion", readonly=True)
    partner_id = fields.Many2one('res.partner', "Proveedor", readonly=True)
    quantity = fields.Float("Cantidad", readonly=True)
    company_id = fields.Many2one('res.company', "Empresa", readonly=True)

    def init(self):
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute("""
            CREATE VIEW %s AS (
                SELECT
                    sm.id AS id,
                    sm.date AS date,
                    sm.product_id AS product_id,
                    t.categ_id AS categ_id,
                    sm.reference AS origin_ref,
                    CASE
                        WHEN sm.production_id IS NOT NULL THEN 'production'
                        -- Una recepcion que viene de la ubicacion de clientes es
                        -- una devolucion, no una compra.
                        WHEN lsrc.usage = 'customer' THEN 'customer_return'
                        ELSE 'purchase'
                    END AS source,
                    pol.order_id AS purchase_order_id,
                    sm.picking_id AS picking_id,
                    sm.production_id AS production_id,
                    COALESCE(sp.partner_id, sm.partner_id) AS partner_id,
                    sm.quantity AS quantity,
                    sm.company_id AS company_id
                FROM stock_move sm
                JOIN product_product p ON p.id = sm.product_id
                JOIN product_template t ON t.id = p.product_tmpl_id
                LEFT JOIN stock_picking_type spt ON spt.id = sm.picking_type_id
                LEFT JOIN stock_picking sp ON sp.id = sm.picking_id
                LEFT JOIN purchase_order_line pol ON pol.id = sm.purchase_line_id
                LEFT JOIN stock_location lsrc ON lsrc.id = sm.location_id
                WHERE sm.state = 'done'
                  AND t.is_storable = true
                  AND (
                      spt.code = 'incoming'
                      -- Solo el producto terminado de la orden: los movimientos de
                      -- materia prima (raw_material_production_id) son consumo.
                      OR sm.production_id IS NOT NULL
                  )
                  -- Una orden desensamblada no deja el producto en bodega: no es
                  -- un ingreso. Se excluye completa, aunque el desensamblaje sea
                  -- parcial.
                  AND NOT EXISTS (
                      SELECT 1 FROM mrp_unbuild ub
                      WHERE ub.mo_id = sm.production_id
                        AND ub.state = 'done'
                  )
            )
        """ % (self._table,))
