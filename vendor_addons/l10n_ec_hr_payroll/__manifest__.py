{
    'name': "l10n_ec_hr_payroll",
    'summary': "Modulo de Nómina Ecuatoriana 2026",
    'description': """
Long description of module's purpose
    """,
    'author': "SCI",
    'website': "https://www.sotomayorconsulting.com",
    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/15.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Human Resources/Payroll',
    'version': '19.0.1.9.0',
    'license': 'LGPL-3',
    # any module necessary for this one to work correctly
    'depends': ['hr_payroll'],
    # always loaded
    'data': [
        # 'security/ir.model.access.csv',
        'data/hr_rule_parameter_data.xml',
        'data/hr_salary_rule_category_data.xml',
        'data/hr_payroll_structure_type_data.xml',
        'views/report_payslip_templates.xml',
        'views/hr_payroll_report.xml',
        'data/hr_payroll_structure_data.xml',
        'data/hr_payslip_input_type_data.xml',
        'data/hr_salary_rule_data.xml',
        'data/hr_payroll_dashboard_warning_data.xml',
        'views/hr_employee_views.xml',
    ],
}

