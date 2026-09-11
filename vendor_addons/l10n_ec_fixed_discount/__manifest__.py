{
    'name': 'Descuento Fijo Ecuador',
    'summary': 'Descuento en monto fijo (USD) en lineas de factura y ordenes de venta',
    'version': '19.0.1.0.0',
    'category': 'Accounting/Localizations',
    'author': 'Sotomayor Consulting International',
    'website': 'https://www.sotomayorconsulting.com',
    'license': 'LGPL-3',
    'depends': ['account', 'sale', 'l10n_ec'],
    'data': [
        'views/account_move_views.xml',
        'views/sale_order_views.xml',
        'views/report_invoice.xml',
    ],
    'installable': True,
    'application': False,
}