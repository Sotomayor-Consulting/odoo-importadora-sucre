{
    'name': 'Gestión de empresas',
    'author': 'Sotomayor Consulting International',
    'version': '19.0.1.0.0',
    'category': 'Custom',
    'depends': ['base','mail'],
    'data': [
        'security/ir.model.access.csv',
        'data/business_structures.xml',
        'data/roles.xml',
        'data/document_types_default.xml',
        'views/entities_view.xml',
        'views/member_line_view.xml',
        'views/member_view.xml',
        'views/entities_registration_menu.xml'
    ],
    'assets': {
        'web.assets_backend': [
            'sci_companies_management/static/src/js/many2many_binary_confirm.js',
            'sci_companies_management/static/src/js/entity_documents_file_viewer.js',
        ],
    },
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
