from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestStockOutflowReport(TransactionCase):

    def test_outflow_row_links_picking_order_and_invoice(self):
        # La facturacion electronica de l10n_ec exige datos de SRI que no hacen
        # al caso de esta vista; se desactiva el EDI en el diario de ventas.
        self.env['account.journal'].search([('type', '=', 'sale')]).edi_format_ids = [(5, 0, 0)]

        product = self.env['product.product'].create({
            'name': 'Rollo de prueba',
            'is_storable': True,
            'list_price': 100.0,
        })
        partner = self.env['res.partner'].create({'name': 'Cliente de prueba'})

        order = self.env['sale.order'].create({
            'partner_id': partner.id,
            'order_line': [(0, 0, {
                'product_id': product.id,
                'product_uom_qty': 4.0,
                'price_unit': 50.0,
                'discount': 10.0,
            })],
        })
        order.action_confirm()

        picking = order.picking_ids
        self.assertTrue(picking, "la confirmacion debe generar la entrega")
        for move in picking.move_ids:
            move.quantity = move.product_uom_qty
            move.picked = True
        picking.button_validate()

        invoice = order._create_invoices()
        invoice.action_post()

        self.env.flush_all()
        rows = self.env['imp.stock.outflow.report'].search([
            ('sale_order_id', '=', order.id),
        ])
        self.assertEqual(len(rows), 1)
        row = rows
        self.assertEqual(row.product_id, product)
        self.assertEqual(row.picking_id, picking)
        self.assertEqual(row.partner_id, partner)
        self.assertEqual(row.invoice_ref, invoice.name)
        self.assertAlmostEqual(row.quantity, 4.0)
        # 4 x 50 menos 10% de descuento
        self.assertAlmostEqual(row.price_total, 180.0)
