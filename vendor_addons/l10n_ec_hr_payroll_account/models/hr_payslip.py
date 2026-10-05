from odoo import models
from odoo.exceptions import UserError


class HrPayslip(models.Model):
    _inherit = "hr.payslip"

    def action_register_payment(self):
        """Extiende el pago estandar (un recibo) para registrar el pago de varios recibos a la vez.
        Abre el mismo asistente de hr_payroll_account: crea un pago por empleado, lo concilia con
        la cuenta del neto y marca cada recibo como pagado."""
        if len(self) <= 1:
            return super().action_register_payment()

        if len(self.company_id) > 1:
            raise UserError(self.env._("Selecciona recibos de una sola empresa."))
        if any(slip.state == "paid" for slip in self):
            raise UserError(self.env._("Solo se puede registrar el pago de recibos que no esten pagados."))
        if any(slip.state != "validated" or not slip.move_id for slip in self):
            raise UserError(self.env._("Solo se pueden pagar recibos validados que tengan asiento contable."))
        if any(move.state != "posted" for move in self.move_id):
            raise UserError(self.env._("Registra (publica) los asientos contables antes de pagar los recibos."))

        net_rules = self.struct_id.rule_ids.filtered(lambda rule: rule.code == "NET").with_company(self.company_id)
        net_accounts = net_rules.account_credit
        if not net_accounts or any(not account.reconcile for account in net_accounts):
            raise UserError(self.env._("La cuenta de credito de la regla NET debe permitir conciliacion."))

        untrusted = self.employee_id.filtered(
            lambda employee: any(not bank.allow_out_payment for bank in employee.sudo().bank_account_ids)
        )
        if untrusted:
            raise UserError(self.env._(
                "Estos empleados tienen una cuenta bancaria no confiable: %(employees)s",
                employees=", ".join(untrusted.mapped("name")),
            ))

        # Solo las lineas del neto: evita pagar al empleado otros pasivos del asiento.
        lines = self.move_id.line_ids.filtered(lambda line: line.account_id in net_accounts and not line.reconciled)
        if not lines:
            raise UserError(self.env._("No hay valores pendientes de pago en los recibos seleccionados."))

        return lines.action_register_payment(ctx={
            "default_company_id": self.company_id.id,
            "payment_consider_partner": True,
            "hr_payroll_payment_register": True,
            "dont_redirect_to_payments": True,
        })