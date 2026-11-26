from collections import defaultdict
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, ValidationError
from odoo.fields import Domain


class ResPartner(models.Model):
    _inherit = 'res.partner'

    overdue_control_exempt = fields.Boolean(
        string='Exempt from Overdue Control',
        company_dependent=True,
        tracking=True,
        help="If checked, this customer is exempt from the overdue invoices block on "
             "sales orders and customer invoices.",
    )
    overdue_control_exempt_reason = fields.Char(
        string='Exemption Reason',
        company_dependent=True,
        tracking=True,
        help="Reason explaining why this customer is exempt from the overdue invoices block.",
    )

    @api.model
    def _commercial_fields(self):
        return super()._commercial_fields() + [
            'overdue_control_exempt',
            'overdue_control_exempt_reason',
        ]

    @api.constrains('overdue_control_exempt', 'overdue_control_exempt_reason')
    def _check_overdue_control_exempt_reason(self):
        for partner in self:
            if partner.overdue_control_exempt and not (partner.overdue_control_exempt_reason or '').strip():
                raise ValidationError(_(
                    "Please provide a reason for exempting %(partner)s from the overdue invoices control.",
                    partner=partner.display_name,
                ))

    def _can_manage_overdue_exemption(self):
        return (
            self.env.su
            or self.env.user.has_group('account_overdue_control.group_overdue_control_bypass')
            or self.env.user.has_group('account.group_account_manager')
        )

    @api.model_create_multi
    def create(self, vals_list):
        if not self._can_manage_overdue_exemption():
            for vals in vals_list:
                if vals.get('overdue_control_exempt') or vals.get('overdue_control_exempt_reason'):
                    parent_id = vals.get('parent_id')
                    parent = self.sudo().browse(parent_id).commercial_partner_id if parent_id else self.env['res.partner']
                    if not (
                        parent
                        and bool(vals.get('overdue_control_exempt')) == bool(parent.overdue_control_exempt)
                        and (vals.get('overdue_control_exempt_reason') or False) == (parent.overdue_control_exempt_reason or False)
                    ):
                        raise AccessError(_(
                            "Only accounting managers or users allowed to bypass overdue control "
                            "can manage customer overdue exemptions."
                        ))
        return super().create(vals_list)

    @api.onchange('overdue_control_exempt')
    def _onchange_overdue_control_exempt(self):
        if not self.overdue_control_exempt:
            self.overdue_control_exempt_reason = False

    def write(self, vals):
        if vals.get('overdue_control_exempt') is False and 'overdue_control_exempt_reason' not in vals:
            vals = dict(vals, overdue_control_exempt_reason=False)
        if (
            ('overdue_control_exempt' in vals or 'overdue_control_exempt_reason' in vals)
            and not self._can_manage_overdue_exemption()
        ):
            for partner in self:
                parent = partner.sudo().parent_id.commercial_partner_id
                new_exempt = vals.get('overdue_control_exempt', partner.overdue_control_exempt)
                new_reason = vals.get('overdue_control_exempt_reason', partner.overdue_control_exempt_reason)
                is_parent_sync = (
                    bool(parent)
                    and bool(new_exempt) == bool(parent.overdue_control_exempt)
                    and (new_reason or False) == (parent.overdue_control_exempt_reason or False)
                )
                if not is_parent_sync:
                    raise AccessError(_(
                        "Only accounting managers or users allowed to bypass overdue control "
                        "can manage customer overdue exemptions."
                    ))
        return super().write(vals)

    def _empty_overdue_status(self):
        return {
            'blocked': False,
            'invoices': self.env['account.move'],
            'lines': self.env['account.move.line'],
            'has_entries': False,
            'amount': 0.0,
            'message': '',
        }

    @api.model
    def _get_overdue_control_status_batch(self, partner_company_pairs, exclude_move_ids=None):
        """Evaluate overdue control status in batch for ``(partner, company)`` pairs.

        Overdue balances are computed from open receivable journal items
        (``account.move.line``) of:
        - Posted customer invoices (``out_invoice``, ``payment_state`` in ``not_paid``/``partial``),
          accurately handling both single-due-date and multi-installment payment terms.
        - Optionally (``company.overdue_include_entries``), posted unreconciled debit
          journal entries (``move_type == 'entry'``, e.g. imported opening receivable balances,
          excluding payment and bank statement entries).

        Partner matching is performed on ``account.move.line.partner_id`` so multi-customer
        opening balance entries (where ``move_id.partner_id`` is empty) are evaluated per
        customer accurately. When ``company.overdue_cutoff_date`` is configured, items whose
        due date (or accounting date if no due date is set) is earlier than the cutoff are
        excluded.

        :returns: dict keyed by ``(commercial_partner_id, company_id)`` with values:
                  ``{'blocked': bool, 'invoices': account.move, 'lines': account.move.line,
                     'has_entries': bool, 'amount': float, 'message': str}``.
        """
        results = {}
        exclude_ids = set(exclude_move_ids or ())
        partners_by_company = defaultdict(set)

        for partner, company in partner_company_pairs:
            if not partner or not company:
                continue
            commercial = partner._origin.commercial_partner_id
            company = company._origin
            if not commercial.id or not company.id:
                continue
            key = (commercial.id, company.id)
            if key in results:
                continue
            results[key] = self._empty_overdue_status()
            company_sudo = company.sudo()
            if not company_sudo.overdue_control_enabled:
                continue
            if commercial.sudo().with_company(company_sudo).overdue_control_exempt:
                continue
            partners_by_company[company_sudo].add(commercial.id)

        if not partners_by_company:
            return results

        today = fields.Date.context_today(self)
        MoveLine = self.env['account.move.line'].sudo()

        for company, partner_ids in partners_by_company.items():
            grace_days = max(company.overdue_grace_days or 0, 0)
            limit_date = today - timedelta(days=grace_days)

            base_domain = Domain([
                ('partner_id.commercial_partner_id', 'in', list(partner_ids)),
                ('company_id', 'child_of', company.root_id.id),
                ('parent_state', '=', 'posted'),
                ('account_type', '=', 'asset_receivable'),
                ('reconciled', '=', False),
                ('amount_residual', '>', 0.0),
            ])

            overdue_date_domain = (
                Domain('date_maturity', '<', limit_date)
                | (Domain('date_maturity', '=', False) & Domain('date', '<', limit_date))
            )

            if company.overdue_cutoff_date:
                cutoff_date = company.overdue_cutoff_date
                overdue_date_domain &= (
                    Domain('date_maturity', '>=', cutoff_date)
                    | (Domain('date_maturity', '=', False) & Domain('date', '>=', cutoff_date))
                )

            invoice_domain = Domain([
                ('move_id.move_type', '=', 'out_invoice'),
                ('move_id.payment_state', 'in', ('not_paid', 'partial')),
            ])
            if company.overdue_include_entries:
                entry_domain = Domain([
                    ('move_id.move_type', '=', 'entry'),
                    ('move_id.origin_payment_id', '=', False),
                    ('move_id.statement_line_id', '=', False),
                ])
                type_domain = invoice_domain | entry_domain
            else:
                type_domain = invoice_domain

            domain = base_domain & overdue_date_domain & type_domain
            if exclude_ids:
                domain &= Domain('move_id', 'not in', list(exclude_ids))

            overdue_lines = MoveLine.search_fetch(domain, ['move_id', 'partner_id', 'amount_residual'])
            if not overdue_lines:
                continue

            overdue_lines.partner_id.fetch(['commercial_partner_id'])
            overdue_lines.move_id.fetch(['move_type'])

            invoice_moves_by_partner = defaultdict(set)
            entry_lines_by_partner = defaultdict(set)
            all_lines_by_partner = defaultdict(set)
            amount_by_partner = defaultdict(float)

            for line in overdue_lines:
                pid = line.partner_id.commercial_partner_id.id
                all_lines_by_partner[pid].add(line.id)
                amount_by_partner[pid] += line.amount_residual
                if line.move_id.move_type == 'out_invoice':
                    invoice_moves_by_partner[pid].add(line.move_id.id)
                else:
                    entry_lines_by_partner[pid].add(line.id)

            currency = company.currency_id
            tolerance = max(company.overdue_tolerance or 0.0, 0.0)
            partner_names = {
                p.id: p.display_name
                for p in self.sudo().browse(list(all_lines_by_partner.keys()))
            }

            for pid, line_ids in all_lines_by_partner.items():
                amount = amount_by_partner[pid]
                if currency.compare_amounts(amount, tolerance) <= 0:
                    continue
                invoice_ids = sorted(invoice_moves_by_partner.get(pid, ()))
                entry_line_ids = entry_lines_by_partner.get(pid, set())
                has_entries = bool(entry_line_ids)
                invoices = self.env['account.move'].browse(invoice_ids)
                lines = self.env['account.move.line'].browse(sorted(line_ids))
                if has_entries:
                    count = len(invoice_ids) + len(entry_line_ids)
                    message = _(
                        "%(partner)s has %(count)s overdue receivable item(s) for a total of %(amount)s.",
                        partner=partner_names[pid],
                        count=count,
                        amount=currency.format(amount),
                    )
                else:
                    message = _(
                        "%(partner)s has %(count)s overdue invoice(s) for a total of %(amount)s.",
                        partner=partner_names[pid],
                        count=len(invoices),
                        amount=currency.format(amount),
                    )
                results[(pid, company.id)] = {
                    'blocked': True,
                    'invoices': invoices,
                    'lines': lines,
                    'has_entries': has_entries,
                    'amount': amount,
                    'message': message,
                }

        return results

    def _get_overdue_control_status(self, company, exclude_ids=None):
        """Evaluate the global overdue control for this customer in ``company``."""
        self.ensure_one()
        commercial = self._origin.commercial_partner_id
        company = company._origin if company else company
        if not commercial.id or not company or not company.id:
            return self._empty_overdue_status()
        statuses = self._get_overdue_control_status_batch(
            [(commercial, company)],
            exclude_move_ids=exclude_ids,
        )
        return statuses.get((commercial.id, company.id), self._empty_overdue_status())

    def _action_view_overdue_invoices(self, invoices, lines=None, has_entries=False):
        if has_entries and lines:
            return {
                'type': 'ir.actions.act_window',
                'name': _('Overdue Receivable Items'),
                'res_model': 'account.move.line',
                'view_mode': 'list,form',
                'domain': [('id', 'in', lines.ids)],
                'context': {'create': False},
            }
        return {
            'type': 'ir.actions.act_window',
            'name': _('Overdue Invoices'),
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [('id', 'in', invoices.ids)],
            'context': {'create': False, 'default_move_type': 'out_invoice'},
        }
