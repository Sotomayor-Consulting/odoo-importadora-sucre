from datetime import timedelta

from odoo.fields import Command
from odoo.tests import TransactionCase, tagged


@tagged('post_install', '-at_install')
class TestServiceTaskAssignment(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env['res.partner'].create({'name': 'Cliente Test'})
        cls.project = cls.env['project.project'].create({'name': 'Proyecto Global'})

        cls.user_categ = cls._create_user('cat')
        cls.user_override = cls._create_user('override')
        cls.user_role = cls._create_user('role')

        cls.role = cls.env['project.role'].create({
            'name': 'Asesor legal',
            'sci_user_id': cls.user_role.id,
        })
        # Categoria con defaults (responsable directo + horas + plazo).
        cls.categ = cls.env['product.category'].create({
            'name': 'Legal',
            'sci_task_user_id': cls.user_categ.id,
            'sci_estimated_hours': 4.0,
            'sci_deadline_days': 5,
        })

        cls.product_default = cls._create_service('Servicio hereda categoria')
        cls.product_override = cls._create_service(
            'Servicio con responsable propio',
            sci_task_user_id=cls.user_override.id,
            sci_estimated_hours=10.0,
            sci_deadline_days=2,
        )
        cls.product_role = cls._create_service(
            'Servicio por rol',
            sci_task_role_id=cls.role.id,
        )

    @classmethod
    def _create_user(cls, suffix):
        return cls.env['res.users'].create({
            'name': f'User {suffix}',
            'login': f'sci_user_{suffix}',
        })

    @classmethod
    def _create_service(cls, name, **extra):
        vals = {
            'name': name,
            'type': 'service',
            'service_tracking': 'task_global_project',
            'project_id': cls.project.id,
            'categ_id': cls.categ.id,
        }
        vals.update(extra)
        return cls.env['product.product'].create(vals)

    def _confirm_order(self, product, qty):
        order = self.env['sale.order'].create({
            'partner_id': self.partner.id,
            'order_line': [Command.create({
                'product_id': product.id,
                'product_uom_qty': qty,
            })],
        })
        order.action_confirm()
        task = order.order_line.task_id
        self.assertTrue(task, "Se debe crear una tarea")
        return order, task

    def test_inherits_from_category(self):
        order, task = self._confirm_order(self.product_default, qty=2)
        self.assertEqual(task.user_ids, self.user_categ)
        self.assertEqual(task.allocated_hours, 8.0)  # 4 h x 2 unidades
        self.assertEqual(
            task.date_deadline.date(),
            (order.date_order + timedelta(days=5)).date(),
        )

    def test_product_overrides_category(self):
        order, task = self._confirm_order(self.product_override, qty=1)
        self.assertEqual(task.user_ids, self.user_override)
        self.assertEqual(task.allocated_hours, 10.0)
        self.assertEqual(
            task.date_deadline.date(),
            (order.date_order + timedelta(days=2)).date(),
        )

    def test_assignment_via_role(self):
        order, task = self._confirm_order(self.product_role, qty=1)
        self.assertEqual(task.user_ids, self.user_role,
                         "La persona debe venir del rol")
        self.assertIn(self.role, task.role_ids)
        self.assertEqual(task.allocated_hours, 4.0)  # hereda horas de la categoria
