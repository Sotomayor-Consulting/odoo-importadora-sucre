{
    'name': 'Tablero de Existencias Importadora Sucre',
    'summary': 'Tablero de hoja de calculo: existencias a fecha, ingresos y salidas',
    'version': '19.0.1.0.0',
    'category': 'Inventory/Inventory',
    'author': 'Sotomayor Consulting International',
    'website': 'https://www.sotomayorconsulting.com',
    'license': 'LGPL-3',
    'depends': [
        'sale_stock',
        'purchase_stock',
        'mrp',
        'account',
        'spreadsheet_dashboard',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/dashboards.xml',
    ],
    'installable': True,
    'application': False,
}
