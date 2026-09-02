from odoo import SUPERUSER_ID, api


def post_init_hook(env):
    if not isinstance(env, api.Environment):
        env = api.Environment(env, SUPERUSER_ID, {})

    fee_product = env.ref('payment_stripe_fee.product_stripe_fee', raise_if_not_found=False)
    if not fee_product:
        return

    stripe_providers = env['payment.provider'].search([
        ('code', '=', 'stripe'),
        ('stripe_fee_product_id', '=', False),
    ])
    stripe_providers.write({'stripe_fee_product_id': fee_product.id})
