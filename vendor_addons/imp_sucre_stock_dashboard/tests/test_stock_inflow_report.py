from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestStockInflowReport(TransactionCase):

    def _product(self, name):
        return self.env['product.product'].create({
            'name': name,
            'is_storable': True,
            'list_price': 10.0,
            'standard_price': 5.0,
        })

    def test_receipt_row_carries_purchase_order(self):
        product = self._product('Materia prima de prueba')
        vendor = self.env['res.partner'].create({'name': 'Proveedor de prueba'})
        order = self.env['purchase.order'].create({
            'partner_id': vendor.id,
            'order_line': [(0, 0, {
                'product_id': product.id,
                'product_qty': 7.0,
                'price_unit': 5.0,
            })],
        })
        order.button_confirm()
        picking = order.picking_ids
        self.assertTrue(picking, "la confirmacion debe generar la recepcion")
        for move in picking.move_ids:
            move.quantity = move.product_uom_qty
            move.picked = True
        picking.button_validate()

        self.env.flush_all()
        rows = self.env['imp.stock.inflow.report'].search([('product_id', '=', product.id)])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows.source, 'purchase')
        self.assertEqual(rows.purchase_order_id, order)
        self.assertEqual(rows.partner_id, vendor)
        self.assertAlmostEqual(rows.quantity, 7.0)

    def _manufacture(self, qty=3.0):
        component = self._product('Componente de prueba')
        finished = self._product('Producto terminado de prueba')
        bom = self.env['mrp.bom'].create({
            'product_tmpl_id': finished.product_tmpl_id.id,
            'product_qty': 1.0,
            'type': 'normal',
            'bom_line_ids': [(0, 0, {'product_id': component.id, 'product_qty': 1.0})],
        })
        production = self.env['mrp.production'].create({
            'product_id': finished.id,
            'product_qty': qty,
            'bom_id': bom.id,
        })
        production.action_confirm()
        production.qty_producing = qty
        for move in production.move_raw_ids:
            move.quantity = move.should_consume_qty
            move.picked = True
        production.button_mark_done()
        return component, finished, bom, production

    def test_manufacturing_order_is_an_inflow_and_its_components_are_not(self):
        component, finished, _bom, production = self._manufacture()

        self.env.flush_all()
        rows = self.env['imp.stock.inflow.report'].search([('product_id', '=', finished.id)])
        self.assertEqual(len(rows), 1, "la orden de produccion debe ser un ingreso")
        self.assertEqual(rows.source, 'production')
        self.assertEqual(rows.production_id, production)
        self.assertAlmostEqual(rows.quantity, 3.0)
        self.assertFalse(rows.purchase_order_id)

        self.assertFalse(
            self.env['imp.stock.inflow.report'].search([('product_id', '=', component.id)]),
            "el consumo de materia prima no es un ingreso")

    def test_unbuilt_manufacturing_order_is_not_an_inflow(self):
        _component, finished, bom, production = self._manufacture()
        unbuild = self.env['mrp.unbuild'].create({
            'mo_id': production.id,
            'product_id': finished.id,
            'bom_id': bom.id,
            'product_qty': 3.0,
        })
        unbuild.action_unbuild()

        self.env.flush_all()
        self.assertFalse(
            self.env['imp.stock.inflow.report'].search([('product_id', '=', finished.id)]),
            "una orden desensamblada no deja producto en bodega")
