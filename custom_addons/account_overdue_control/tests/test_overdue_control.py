from datetime import timedelta

from odoo import fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import Form, tagged

from odoo.addons.account.tests.common import AccountTestInvoicingCommon


@tagged('post_install', '-at_install')
class TestOverdueControl(AccountTestInvoicingCommon):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.today = fields.Date.context_today(cls.env.user)
        cls.env.user.group_ids += cls.env.ref('sales_team.group_sale_salesman')

        cls.term_30_days = cls.env['account.payment.term'].create({
            'name': '30 days',
            'line_ids': [(0, 0, {'value': 'percent', 'value_amount': 100, 'nb_days': 30})],
        })
        cls.term_immediate = cls.env['account.payment.term'].create({
            'name': 'Immediate',
            'line_ids': [(0, 0, {'value': 'percent', 'value_amount': 100, 'nb_days': 0})],
        })
        cls.term_split = cls.env['account.payment.term'].create({
            'name': '50% 15 days / 50% 45 days',
            'line_ids': [
                (0, 0, {'value': 'percent', 'value_amount': 50, 'nb_days': 15}),
                (0, 0, {'value': 'percent', 'value_amount': 50, 'nb_days': 45}),
            ],
        })

        # Ensure global overdue control is enabled with default strict rules (0 grace days, 0 tolerance).
        cls.company_data['company'].write({
            'overdue_control_enabled': True,
            'overdue_grace_days': 0,
            'overdue_tolerance': 0.0,
            'overdue_include_entries': True,
            'overdue_cutoff_date': False,
        })

        # Overdue invoice for partner_a: 30-day term issued 40 days ago -> 10 days past due.
        cls.old_invoice = cls.init_invoice(
            'out_invoice',
            partner=cls.partner_a,
            amounts=[1000.0],
            invoice_date=cls.today - timedelta(days=40),
            post=False,
        )
        cls.old_invoice.invoice_payment_term_id = cls.term_30_days
        cls.old_invoice.with_context(skip_overdue_control=True).action_post()

    def _new_invoice(self, partner=None, term=False, invoice_date=None, amounts=None):
        invoice = self.init_invoice(
            'out_invoice',
            partner=partner or self.partner_a,
            amounts=amounts or [100.0],
            invoice_date=invoice_date or self.today,
            post=False,
        )
        invoice.invoice_payment_term_id = term
        return invoice

    def _new_sale_order(self, partner=None, term=False):
        return self.env['sale.order'].create({
            'partner_id': (partner or self.partner_a).id,
            'payment_term_id': term.id if term else False,
            'order_line': [(0, 0, {'product_id': self.product_a.id, 'product_uom_qty': 1})],
        })

    def test_global_block_regardless_of_new_payment_term(self):
        """Customer with overdue invoice is blocked even with Immediate or no payment term."""
        for term in (self.term_30_days, self.term_immediate, False):
            invoice = self._new_invoice(term=term)
            self.assertTrue(invoice.overdue_control_blocked)
            with self.assertRaises(UserError):
                invoice.action_post()

    def test_due_today_is_not_blocked_and_due_yesterday_is_blocked(self):
        """Invoice due today is not past due yet; due yesterday triggers the block."""
        due_today = self._new_invoice(
            partner=self.partner_b,
            term=self.term_30_days,
            invoice_date=self.today - timedelta(days=30),
        )
        due_today.action_post()

        check_inv = self._new_invoice(partner=self.partner_b)
        self.assertFalse(check_inv.overdue_control_blocked)

        due_yesterday = self._new_invoice(
            partner=self.partner_b,
            term=self.term_30_days,
            invoice_date=self.today - timedelta(days=31),
        )
        due_yesterday.with_context(skip_overdue_control=True).action_post()

        check_inv.invalidate_recordset()
        self.assertTrue(check_inv.overdue_control_blocked)
        with self.assertRaises(UserError):
            check_inv.action_post()

    def test_multi_installment_payment_term_blocks_on_first_overdue_installment(self):
        """First installment overdue (15d) blocks even though final due date (45d) is in the future."""
        split_inv = self._new_invoice(
            partner=self.partner_b,
            term=self.term_split,
            invoice_date=self.today - timedelta(days=20),
            amounts=[1000.0],
        )
        split_inv.action_post()

        # Final invoice_date_due is 25 days in the future, yet installment 1 is 5 days overdue.
        self.assertGreater(split_inv.invoice_date_due, self.today)
        new_inv = self._new_invoice(partner=self.partner_b)
        self.assertTrue(new_inv.overdue_control_blocked)
        with self.assertRaises(UserError):
            new_inv.action_post()

    def test_sale_order_confirmation_blocked_and_stays_quotation(self):
        """Sales order shows alert and cannot be confirmed, remaining in quotation state."""
        order = self._new_sale_order(term=self.term_immediate)
        self.assertTrue(order.overdue_control_blocked)
        self.assertTrue(order.overdue_control_message)
        with self.assertRaises(UserError):
            order.action_confirm()
        self.assertEqual(order.state, 'draft')

    def test_grace_days_rule(self):
        """Company grace days delay blocking until due_date + grace_days < today."""
        self.company_data['company'].overdue_grace_days = 15  # old_invoice is 10 days overdue
        invoice = self._new_invoice()
        order = self._new_sale_order()
        self.assertFalse(invoice.overdue_control_blocked)
        self.assertFalse(order.overdue_control_blocked)
        order.action_confirm()
        self.assertEqual(order.state, 'sale')
        invoice.action_post()
        self.assertEqual(invoice.state, 'posted')

    def test_tolerance_rule(self):
        """Company tolerance allows overdue balances up to the configured threshold."""
        self.company_data['company'].overdue_tolerance = 5000.0
        invoice = self._new_invoice()
        order = self._new_sale_order()
        self.assertFalse(invoice.overdue_control_blocked)
        self.assertFalse(order.overdue_control_blocked)

    def test_exempt_partner_requires_reason_and_unblocks(self):
        """Exempting a customer requires a mandatory reason and unblocks SO and invoices."""
        with self.assertRaises(ValidationError):
            self.partner_a.write({'overdue_control_exempt': True})

        self.partner_a.write({
            'overdue_control_exempt': True,
            'overdue_control_exempt_reason': 'Key strategic account under payment agreement',
        })
        order = self._new_sale_order()
        invoice = self._new_invoice()
        self.assertFalse(order.overdue_control_blocked)
        self.assertFalse(invoice.overdue_control_blocked)
        order.action_confirm()
        invoice.action_post()
        self.assertEqual(order.state, 'sale')
        self.assertEqual(invoice.state, 'posted')

    def test_unauthorized_user_cannot_modify_partner_exemption(self):
        """Salesperson without manager/bypass group cannot exempt a customer."""
        sales_user = self.env['res.users'].create({
            'name': 'Regular Salesperson',
            'login': 'regular_salesperson_overdue',
            'email': 'sales@example.com',
            'group_ids': [(6, 0, [self.env.ref('sales_team.group_sale_salesman').id])],
        })
        with self.assertRaises(AccessError):
            self.partner_a.with_user(sales_user).write({
                'overdue_control_exempt': True,
                'overdue_control_exempt_reason': 'Unauthorized attempt',
            })

    def test_paid_invoice_is_not_overdue(self):
        self.env['account.payment.register'].with_context(
            active_model='account.move',
            active_ids=self.old_invoice.ids,
        ).create({})._create_payments()
        invoice = self._new_invoice()
        order = self._new_sale_order()
        self.assertFalse(invoice.overdue_control_blocked)
        self.assertFalse(order.overdue_control_blocked)

    def test_contact_of_company_is_blocked(self):
        contact = self.env['res.partner'].create({'name': 'Contact A', 'parent_id': self.partner_a.id})
        invoice = self._new_invoice(partner=contact)
        order = self._new_sale_order(partner=contact)
        self.assertTrue(invoice.overdue_control_blocked)
        self.assertTrue(order.overdue_control_blocked)

    def test_bypass_group_requires_reason_on_invoice_and_wizard_logs_reason(self):
        """Bypass group cannot post without a reason; wizard records reason and posts."""
        self.env.user.group_ids += self.env.ref('account_overdue_control.group_overdue_control_bypass')
        invoice = self._new_invoice()

        with self.assertRaises(UserError):
            invoice.action_post()

        action = invoice.action_open_overdue_bypass_wizard()
        wizard = self.env['account.overdue.bypass.wizard'].with_context(action['context']).create({
            'reason': 'Approved by Finance Director - payment transfer confirmed',
        })
        wizard.action_confirm_bypass()

        self.assertEqual(invoice.state, 'posted')
        self.assertEqual(
            invoice.overdue_bypass_reason,
            'Approved by Finance Director - payment transfer confirmed',
        )
        self.assertEqual(invoice.overdue_bypass_user_id, self.env.user)
        self.assertTrue(invoice.overdue_bypass_date)
        self.assertTrue(
            any('Approved by Finance Director' in (m.body or '') for m in invoice.message_ids)
        )

    def test_bypass_group_requires_reason_on_sale_order_and_wizard_logs_reason(self):
        """Bypass group cannot confirm SO without a reason; wizard records reason and confirms."""
        self.env.user.group_ids += self.env.ref('account_overdue_control.group_overdue_control_bypass')
        order = self._new_sale_order()

        with self.assertRaises(UserError):
            order.action_confirm()
        self.assertEqual(order.state, 'draft')

        action = order.action_open_overdue_bypass_wizard()
        wizard = self.env['account.overdue.bypass.wizard'].with_context(action['context']).create({
            'reason': 'Urgent delivery approved by General Manager',
        })
        wizard.action_confirm_bypass()

        self.assertEqual(order.state, 'sale')
        self.assertEqual(
            order.overdue_bypass_reason,
            'Urgent delivery approved by General Manager',
        )
        self.assertEqual(order.overdue_bypass_user_id, self.env.user)
        self.assertTrue(order.overdue_bypass_date)
        self.assertTrue(
            any('Urgent delivery approved by General Manager' in (m.body or '') for m in order.message_ids)
        )

    def test_sudo_does_not_silently_bypass_block(self):
        """Calling sudo().action_post() as a non-bypass user still enforces the block."""
        invoice = self._new_invoice()
        with self.assertRaises(UserError):
            invoice.sudo().action_post()

    def test_reset_to_draft_clears_bypass_reason(self):
        """Resetting a bypassed invoice to draft clears the previous bypass authorization."""
        self.env.user.group_ids += self.env.ref('account_overdue_control.group_overdue_control_bypass')
        invoice = self._new_invoice()
        action = invoice.action_open_overdue_bypass_wizard()
        self.env['account.overdue.bypass.wizard'].with_context(action['context']).create({
            'reason': 'Initial approval',
        }).action_confirm_bypass()
        self.assertEqual(invoice.state, 'posted')

        invoice.button_draft()
        self.assertFalse(invoice.overdue_bypass_reason)
        with self.assertRaises(UserError):
            invoice.action_post()

    def test_credit_note_is_never_blocked(self):
        """Customer credit notes (out_refund) are not blocked by overdue control."""
        credit_note = self.init_invoice(
            'out_refund',
            partner=self.partner_a,
            amounts=[100.0],
            invoice_date=self.today,
            post=False,
        )
        self.assertFalse(credit_note.overdue_control_blocked)
        credit_note.action_post()
        self.assertEqual(credit_note.state, 'posted')

    def test_sale_order_form_reactive_banner(self):
        """Quotation form immediately flags blocked status on partner selection."""
        form = Form(self.env['sale.order'])
        form.partner_id = self.partner_a
        self.assertTrue(form.overdue_control_blocked)
        self.assertTrue(form.overdue_control_message)

    def _create_opening_receivable_entry(self, line_specs, entry_date=None):
        """Create a posted multi-partner journal entry (move_type='entry') against AR.

        ``line_specs`` is a list of dicts: ``{'partner': partner, 'debit': float, 'credit': float, 'date_maturity': date|False}``.
        """
        receivable = self.company_data['default_account_receivable']
        counterpart = self.company_data['default_account_revenue']
        journal = self.company_data['default_journal_misc']
        move_lines = []
        net_balance = 0.0
        for spec in line_specs:
            debit = spec.get('debit', 0.0)
            credit = spec.get('credit', 0.0)
            net_balance += debit - credit
            vals = {
                'account_id': receivable.id,
                'partner_id': spec['partner'].id,
                'debit': debit,
                'credit': credit,
                'name': spec.get('name', 'Imported AR balance'),
            }
            if 'date_maturity' in spec:
                vals['date_maturity'] = spec['date_maturity']
            move_lines.append((0, 0, vals))
        move_lines.append((0, 0, {
            'account_id': counterpart.id,
            'debit': max(-net_balance, 0.0),
            'credit': max(net_balance, 0.0),
            'name': 'Opening balance counterpart',
        }))
        entry = self.env['account.move'].create({
            'move_type': 'entry',
            'journal_id': journal.id,
            'date': entry_date or (self.today - timedelta(days=60)),
            'line_ids': move_lines,
        })
        entry.action_post()
        return entry

    def test_imported_multi_partner_receivable_entry_blocks_only_overdue_partner(self):
        """Multi-partner imported entry (move.partner_id=False) blocks only the overdue customer and opens move lines."""
        partner_c = self.env['res.partner'].create({'name': 'Partner C'})
        self._create_opening_receivable_entry([
            {'partner': self.partner_b, 'debit': 400.0, 'date_maturity': self.today - timedelta(days=15)},
            {'partner': partner_c, 'debit': 300.0, 'date_maturity': self.today + timedelta(days=15)},
        ])

        inv_b = self._new_invoice(partner=self.partner_b)
        inv_c = self._new_invoice(partner=partner_c)
        self.assertTrue(inv_b.overdue_control_blocked)
        self.assertFalse(inv_c.overdue_control_blocked)
        with self.assertRaises(UserError):
            inv_b.action_post()

        action = inv_b.action_view_overdue_invoices()
        self.assertEqual(action['res_model'], 'account.move.line')

        # Disabling overdue_include_entries stops blocking on journal entries.
        self.company_data['company'].overdue_include_entries = False
        inv_b.invalidate_recordset()
        self.assertFalse(inv_b.overdue_control_blocked)

    def test_imported_entry_without_maturity_uses_accounting_date_and_cutoff_excludes_old(self):
        """Imported entry without date_maturity uses entry date, and overdue_cutoff_date excludes very old items."""
        old_date = self.today - timedelta(days=400)
        self._create_opening_receivable_entry(
            [{'partner': self.partner_b, 'debit': 250.0, 'date_maturity': False}],
            entry_date=old_date,
        )

        inv_b = self._new_invoice(partner=self.partner_b)
        self.assertTrue(inv_b.overdue_control_blocked)

        # Configure cutoff date to exclude historical items older than 180 days.
        self.company_data['company'].overdue_cutoff_date = self.today - timedelta(days=180)
        inv_b.invalidate_recordset()
        self.assertFalse(inv_b.overdue_control_blocked)

        # Recent overdue invoice for partner_a (due 10 days ago) is still blocked.
        inv_a = self._new_invoice(partner=self.partner_a)
        self.assertTrue(inv_a.overdue_control_blocked)

    def test_imported_credit_balance_entry_does_not_block(self):
        """Customer advance / credit balance in an imported AR entry never triggers a block."""
        self._create_opening_receivable_entry([
            {'partner': self.partner_b, 'credit': 500.0, 'date_maturity': self.today - timedelta(days=30)},
        ])
        inv_b = self._new_invoice(partner=self.partner_b)
        self.assertFalse(inv_b.overdue_control_blocked)

