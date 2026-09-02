{
    'name': 'Payment Provider: Wire Transfer',
    'summary': 'Wire transfer provider with receipt and reference capture',
    'description': 'Adds a wire transfer payment provider that supports transfer instructions and optional mandatory upload of receipt and payment reference.',
    'author': 'Sotomayor Consulting International',
    'website': 'https://www.sotomayorconsulting.com',
    'category': 'Accounting/Payment Providers',
    'version': '19.0.1.0.0',
    'license': 'LGPL-3',
    'depends': ['payment', 'sale_management', 'account', 'mail'],
    'data': [
        'views/res_bank_views.xml',
        'views/res_partner_bank_views.xml',
        'views/payment_provider_views.xml',
        'views/payment_transaction_views.xml',
        'views/payment_templates.xml',
        'data/payment_provider_data.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'wire_transfer_provider/static/src/js/wire_transfer_payment_form.js',
        ],
    },
    'installable': True,
    'application': False,
}
