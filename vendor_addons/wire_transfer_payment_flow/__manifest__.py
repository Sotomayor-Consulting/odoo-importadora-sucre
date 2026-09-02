{
    'name': 'Wire Transfer Payment Flow',
    'summary': 'Multi-company flow for deferred transfer reconciliation',
    'description': 'Implements a multi-company payment flow where deferred transfer transactions remain pending until bank reconciliation, while instant providers keep immediate confirmation behavior.',
    'author': 'Sotomayor Consulting International',
    'website': 'https://www.sotomayorconsulting.com',
    'category': 'Accounting/Payment Providers',
    'version': '19.0.1.0.0',
    'license': 'LGPL-3',
    'depends': ['sale_management', 'sale_project', 'account', 'payment', 'project', 'mail'],
    'data': [
        'views/res_partner_views.xml',
        'views/sale_order_views.xml',
    ],
    'installable': True,
    'application': False,
}
