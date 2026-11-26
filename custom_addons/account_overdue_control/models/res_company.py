from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    overdue_control_enabled = fields.Boolean(
        string='Block Customers with Overdue Invoices',
        default=True,
        help="When enabled, all customers with posted unpaid invoices past their payment term "
             "due date (plus grace days) and exceeding the tolerated amount are blocked from "
             "confirming sales orders and posting new customer invoices.",
    )
    overdue_grace_days = fields.Integer(
        string='Overdue Grace Days',
        default=0,
        help="Number of days after an invoice installment due date before it is considered overdue. "
             "0 means any unpaid installment past its payment term due date triggers the block.",
    )
    overdue_tolerance = fields.Monetary(
        string='Tolerated Overdue Amount',
        currency_field='currency_id',
        default=0.0,
        help="Overdue balance (in company currency) allowed before blocking the customer. "
             "0 means any overdue amount triggers the block.",
    )
    overdue_include_entries = fields.Boolean(
        string='Include Receivable Journal Entries',
        default=True,
        help="Include posted unreconciled debit journal items (e.g. imported opening balances "
             "against accounts receivable) when evaluating overdue customer debt.",
    )
    overdue_cutoff_date = fields.Date(
        string='Exclude Overdue Items Older Than',
        help="Optional cutoff date. Unpaid invoices or imported receivable journal entries whose "
             "due date (or accounting date when no due date is set) is earlier than this date "
             "will be excluded from the overdue block.",
    )

    _check_overdue_grace_days = models.Constraint(
        'CHECK(overdue_grace_days >= 0)',
        'Overdue grace days must be greater than or equal to 0.',
    )
    _check_overdue_tolerance = models.Constraint(
        'CHECK(overdue_tolerance >= 0)',
        'Tolerated overdue amount must be greater than or equal to 0.',
    )
