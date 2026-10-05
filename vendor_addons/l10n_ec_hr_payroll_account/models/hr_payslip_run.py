from odoo import models
from odoo.exceptions import UserError


class HrPayslipRun(models.Model):
    _inherit = "hr.payslip.run"

    def action_register_payment(self):
        """Registra el pago de todos los recibos validados del lote."""
        self.ensure_one()
        payslips = self.slip_ids.filtered(lambda slip: slip.state == "validated" and slip.move_id)
        if not payslips:
            raise UserError(self.env._("El lote no tiene recibos validados pendientes de pago."))
        return payslips.action_register_payment()
