from odoo import fields, models, tools


class StockOutflowReport(models.Model):
    """Salidas de inventario con la orden de entrega, la venta y la factura.

    Ningun modelo del core cruza las tres cosas: stock.report no conoce la venta
    ni la factura, y sale.report no conoce el albaran.
    """
    _name = 'imp.stock.outflow.report'
    _description = "Salidas de inventario"
    _auto = False
    _order = 'date desc'

    date = fields.Datetime("Fecha", readonly=True)
    product_id = fields.Many2one('product.product', "Producto", readonly=True)
    categ_id = fields.Many2one('product.category', "Categoria del producto", readonly=True)
    picking_id = fields.Many2one('stock.picking', "Orden de entrega", readonly=True)
    sale_order_id = fields.Many2one('sale.order', "Orden de venta", readonly=True)
    partner_id = fields.Many2one('res.partner', "Cliente", readonly=True)
    invoice_ref = fields.Char("Factura", readonly=True)
    quantity = fields.Float("Cantidad", readonly=True)
    price_total = fields.Monetary("Total", currency_field='currency_id', readonly=True)
    currency_id = fields.Many2one('res.currency', "Moneda", readonly=True)
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
                    sm.picking_id AS picking_id,
                    sol.order_id AS sale_order_id,
                    COALESCE(so.partner_id, sp.partner_id, sm.partner_id) AS partner_id,
                    inv.names AS invoice_ref,
                    sm.quantity AS quantity,
                    sm.quantity * COALESCE(sol.price_unit, 0.0)
                        * (1.0 - COALESCE(sol.discount, 0.0) / 100.0) AS price_total,
                    COALESCE(so.currency_id, c.currency_id) AS currency_id,
                    sm.company_id AS company_id
                FROM stock_move sm
                JOIN stock_picking_type spt ON spt.id = sm.picking_type_id
                JOIN product_product p ON p.id = sm.product_id
                JOIN product_template t ON t.id = p.product_tmpl_id
                LEFT JOIN res_company c ON c.id = sm.company_id
                LEFT JOIN stock_picking sp ON sp.id = sm.picking_id
                LEFT JOIN sale_order_line sol ON sol.id = sm.sale_line_id
                LEFT JOIN sale_order so ON so.id = sol.order_id
                LEFT JOIN LATERAL (
                    SELECT string_agg(DISTINCT am.name, ', ') AS names
                    FROM sale_order_line_invoice_rel r
                    JOIN account_move_line aml ON aml.id = r.invoice_line_id
                    JOIN account_move am ON am.id = aml.move_id
                    WHERE r.order_line_id = sol.id
                      AND am.state = 'posted'
                ) inv ON TRUE
                WHERE sm.state = 'done'
                  AND spt.code = 'outgoing'
                  AND t.is_storable = true
            )
        """ % (self._table,))
