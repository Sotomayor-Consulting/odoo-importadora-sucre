from odoo.tests import Form, TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestTemplatePricing(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env['res.partner'].create({'name': 'Cliente Test'})
        cls.product_a = cls.env['product.product'].create({
            'name': 'Servicio A',
            'type': 'service',
            'list_price': 100.0,
        })
        cls.product_b = cls.env['product.product'].create({
            'name': 'Servicio B',
            'type': 'service',
            'list_price': 50.0,
        })
        cls.product_c = cls.env['product.product'].create({
            'name': 'Servicio C incluido',
            'type': 'service',
            'list_price': 80.0,
        })
        cls.template = cls.env['sale.order.template'].create({
            'name': 'Plantilla Test',
            'sale_order_template_line_ids': [
                (0, 0, {
                    'product_id': cls.product_a.id,
                    'product_uom_qty': 2,
                    'price_unit': 250.0,
                }),
                (0, 0, {
                    'product_id': cls.product_c.id,
                    'product_uom_qty': 1,
                    'price_unit': 0.0,
                }),
                (0, 0, {
                    'display_type': 'line_section',
                    'name': 'Seccion oculta',
                    'collapse_prices': True,
                }),
                (0, 0, {
                    'product_id': cls.product_b.id,
                    'product_uom_qty': 1,
                }),
            ],
        })

    def _order_from_template(self):
        order_form = Form(self.env['sale.order'])
        order_form.partner_id = self.partner
        order_form.sale_order_template_id = self.template
        return order_form.save()

    def test_template_line_autofills_price_from_product(self):
        line_b = self.template.sale_order_template_line_ids.filtered(
            lambda l: l.product_id == self.product_b)
        self.assertEqual(line_b.price_unit, 50.0,
                         "El precio debe autocompletarse desde el producto")

    def test_template_line_keeps_manual_price(self):
        line_a = self.template.sale_order_template_line_ids.filtered(
            lambda l: l.product_id == self.product_a)
        self.assertEqual(line_a.price_unit, 250.0,
                         "Un precio editado manualmente no debe sobrescribirse")

    def test_price_applied(self):
        order = self._order_from_template()
        line_a = order.order_line.filtered(lambda l: l.product_id == self.product_a)
        self.assertEqual(line_a.price_unit, 250.0, "El precio de la plantilla debe persistir")

    def test_zero_price_is_free_in_order(self):
        order = self._order_from_template()
        line_c = order.order_line.filtered(lambda l: l.product_id == self.product_c)
        self.assertEqual(line_c.price_unit, 0.0,
                         "Un precio 0 en la plantilla debe quedar en 0 (incluido gratis)")

    def test_line_without_template_price_uses_product(self):
        order = self._order_from_template()
        line_b = order.order_line.filtered(lambda l: l.product_id == self.product_b)
        self.assertEqual(line_b.price_unit, 50.0, "Sin precio en plantilla se usa el del producto")

    def test_collapse_prices_propagated(self):
        order = self._order_from_template()
        section = order.order_line.filtered(lambda l: l.display_type == 'line_section')
        self.assertTrue(section.collapse_prices, "collapse_prices debe propagarse a la seccion")
