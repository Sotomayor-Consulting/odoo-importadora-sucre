# Part of Odoo. See LICENSE file for full copyright and licensing details.

import logging

from . import controllers
from . import models

from odoo.addons.payment import setup_provider, reset_payment_provider

_logger = logging.getLogger(__name__)


def _post_init_hook(env):
    setup_provider(env, 'payphone')
    _setup_payphone_fee_product(env)


def _payphone_resolve_fee_account(env, company):
    """Cuenta 'Cargo Por Payphone' por su codigo 410118 EN la compania (el codigo es
    company-dependent), con respaldo al id 7476."""
    account = env['account.account'].with_company(company).search(
        [('code', '=', '410118')], limit=1)
    return account or env['account.account'].browse(7476).exists()


def _payphone_resolve_fee_tax(env, company):
    """IVA 15% de venta de la compania, con respaldo al id 165."""
    tax = env['account.tax'].search([
        ('type_tax_use', '=', 'sale'),
        ('amount_type', '=', 'percent'),
        ('amount', '=', 15.0),
        ('company_id', '=', company.id),
    ], limit=1)
    return tax or env['account.tax'].browse(165).exists()


def _setup_payphone_fee_product(env):
    """Configura impuesto y cuenta del producto del fee (xml: payphone.product_payphone_fee)
    y lo asigna por defecto a los proveedores Payphone que no tengan producto.

    El producto se crea por XML (data/product_data.xml); aqui solo se establecen el IVA
    y la cuenta (company-dependent) por la compania de cada proveedor Payphone, y la
    asignacion por defecto al proveedor.
    """
    fee_product = env.ref('payphone.product_payphone_fee', raise_if_not_found=False)
    if not fee_product:
        return

    providers = env['payment.provider'].search([('code', '=', 'payphone')])
    companies = providers.company_id or env.company

    for company in companies:
        product = fee_product.with_company(company)
        vals = {}

        account = _payphone_resolve_fee_account(env, company)
        if account:
            if not product.property_account_income_id:
                vals['property_account_income_id'] = account.id
            if not product.property_account_expense_id:
                vals['property_account_expense_id'] = account.id
        else:
            _logger.warning(
                "Payphone (%s): no se encontro la cuenta del fee (codigo 410118 / id 7476); "
                "el producto usara la cuenta por defecto de su categoria.",
                company.display_name,
            )

        tax = _payphone_resolve_fee_tax(env, company)
        if tax and not product.taxes_id:
            vals['taxes_id'] = [(6, 0, tax.ids)]
        elif not tax:
            _logger.warning(
                "Payphone (%s): no se encontro el IVA 15 de venta (id 165); "
                "el producto del fee quedara sin impuesto.",
                company.display_name,
            )

        if vals:
            product.write(vals)

    providers.filtered(lambda p: not p.payphone_fee_product_id).write(
        {'payphone_fee_product_id': fee_product.id})


def _uninstall_hook(env):
    reset_payment_provider(env, 'payphone')
