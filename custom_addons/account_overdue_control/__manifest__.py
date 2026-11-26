# -*- coding: utf-8 -*-
{
    'name': 'Overdue Invoice Control',
    'summary': 'Globally block sales order confirmation and customer invoicing when a customer has '
               'overdue invoices past their payment term due dates, with configurable grace days, '
               'tolerance, customer exemptions, and audited bypass with mandatory reason.',
    'version': '19.0.2.0.0',
    'author': 'Sotomayor Consulting International',
    'category': 'Accounting/Accounting',
    'license': 'LGPL-3',
    'depends': ['account', 'sale'],
    'data': [
        'security/security.xml',
        'security/ir.model.access.csv',
        'views/res_config_settings_views.xml',
        'views/res_partner_views.xml',
        'views/account_move_views.xml',
        'views/sale_order_views.xml',
        'views/overdue_bypass_wizard_views.xml',
    ],
    'installable': True,
    'application': False,
}
