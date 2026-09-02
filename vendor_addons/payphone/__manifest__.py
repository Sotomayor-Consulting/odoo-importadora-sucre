{
    'name': "Payphone Payment Provider",
    'summary': "Payment provider: Payphone (Ecuador)",
    'description': """
        Integración con Payphone como proveedor de pago para Odoo.
        Soporta pagos con tarjeta de crédito/débito y billetera Payphone
        mediante flujo de redirección.

        Compatible con Ecuador (USD).
    """,
    'author': "SCI",
    'website': "https://www.payphone.app",
    'category': 'Accounting/Payment Providers',
    'version': '19.0.1.0.0',
    'depends': ['payment', 'sale', 'account_payment', 'l10n_ec', 'product'],
    'data': [
        'data/product_data.xml',
        'views/payment_payphone_templates.xml',
        'views/payment_provider_views.xml',
        'views/payment_transaction_views.xml',
        'data/payment_provider_data.xml',
    ],
    'assets': {
        'web.assets_frontend': [
            'payphone/static/src/interactions/payment_form.js',
            'payphone/static/src/js/payphone_fee.js',
        ],
    },
    'post_init_hook': '_post_init_hook',
    'uninstall_hook': '_uninstall_hook',
    'license': 'LGPL-3',
}
