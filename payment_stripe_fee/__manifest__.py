{
    'name': 'Stripe Payment Fee',
    'author': 'Sotomayor Consulting International',
    'version': '1.0',
    'category': 'Accounting/Payment Providers',
    'depends': ['payment', 'payment_stripe', 'account_payment', 'l10n_ec_edi'],
    'data': [
        'data/product_data.xml',
        'views/payment_provider_views.xml',
        'views/payment_transaction_views.xml',
        'views/payment_templates.xml',
    ],
    'post_init_hook': 'post_init_hook',
    'assets': {
        'web.assets_frontend': [
            'payment_stripe_fee/static/src/js/payment_fee.js',
        ],
    },
    'installable': True,
    'license': 'LGPL-3',
}
