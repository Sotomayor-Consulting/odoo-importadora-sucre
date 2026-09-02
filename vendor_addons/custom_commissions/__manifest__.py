{
    'name': 'Gestion de Comisiones',
    'summary': 'Calculo mensual de comisiones por equipo CRM con integracion a nomina',
    'description': """
Gestion de comisiones de Sotomayor Consulting.

Calcula comisiones mensuales por equipo de ventas (crm.team) sobre el
cobrado efectivo conciliado en banco, con tasas configurables por
producto/categoria y deduccion de sueldo base. Soporta comisiones por
rol en producto (ej. EIN, preparador de impuestos) y ajustes manuales
(Trust Pilot). Empuja el total a la nomina ecuatoriana via el input
COMMISSION_TOTAL.
    """,
    'author': 'Sotomayor Consulting International',
    'website': 'https://www.sotomayorconsulting.com',
    'category': 'Human Resources/Payroll',
    'version': '19.0.1.3.0',
    'license': 'LGPL-3',
    'depends': [
        'sale_management',
        'sale_project',
        'account',
        'project',
        'analytic',
        'crm',
        'hr',
        'mail',
        'payment',
        # 'hr_payroll',           # se re-agregan en Fase 6 (integracion nomina)
        # 'l10n_ec_hr_payroll',
    ],
    'data': [
        'security/commission_security.xml',
        'security/ir.model.access.csv',
        'views/commission_rate_rule_views.xml',
        'views/commission_sheet_views.xml',
        'views/commission_line_views.xml',
        'views/commission_detail_line_views.xml',
        'views/crm_team_views.xml',
        'views/hr_employee_views.xml',
        'views/commission_menus.xml',
    ],
    'installable': True,
    'application': True,
}
