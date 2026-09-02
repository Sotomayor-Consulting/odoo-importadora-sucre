{
    'name': 'Referral Partner Commissions',
    'summary': 'Programa de partners referidos: codigo unico, asignacion de clientes y comisiones',
    'description': 'Gestiona el Acuerdo de Colaboracion y Referidos de SCI: partners externos'
                   ' con codigo unico que refieren clientes y ganan comision sobre los'
                   ' honorarios cobrados, liquidada mensualmente como factura de proveedor.'
                   ' Toma las bases del modulo nativo partner_commission (referrer + plan +'
                   ' reglas) sin depender de website/suscripciones/purchase.',
    'author': 'Sotomayor Consulting International',
    'website': 'https://www.sotomayorconsulting.com',
    'category': 'Sales/Sales',
    'version': '19.0.1.0.0',
    'license': 'LGPL-3',
    'depends': ['sale_management', 'account'],
    'data': [
        'security/ir.model.access.csv',
        'data/referral_plan_data.xml',
        'views/referral_partner_convert_views.xml',
        'views/res_partner_views.xml',
        'views/sale_order_views.xml',
        'views/referral_menus.xml',
        'views/referral_commission_plan_views.xml',
        'views/referral_commission_views.xml',
        'views/referral_commission_settlement_views.xml',
        'views/account_move_views.xml',
        'views/product_views.xml',
    ],
    'installable': True,
    'application': False,
}
