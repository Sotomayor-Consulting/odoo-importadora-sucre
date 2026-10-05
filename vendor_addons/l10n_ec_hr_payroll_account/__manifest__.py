{
    'name': 'Ecuador - Nómina con contabilidad',
    'summary': 'Cuentas contables de las reglas de nómina de Ecuador según el plan de cuentas estándar',
    'author': 'Sotomayor Consulting International',
    'website': 'https://www.sotomayorconsulting.com',
    'category': 'Human Resources/Payroll',
    'version': '19.0.1.3.0',
    'license': 'LGPL-3',
    'countries': ['ec'],
    'depends': ['hr_payroll_account', 'l10n_ec', 'l10n_ec_hr_payroll'],
    'data': [
        'data/l10n_ec_hr_payroll_account_data.xml',
        'data/hr_salary_rule_data.xml',
        'data/ir_actions_server_data.xml',
        'data/hr_payroll_dashboard_warning_data.xml',
        'views/hr_payslip_run_views.xml',
    ],
    'auto_install': True,
}
