{
    'name': 'Quotation Template Pricing',
    'summary': 'Precio unitario, descuento y ocultar precios en plantillas de cotizacion',
    'description': 'Anade precio unitario y descuento editables a las lineas de las'
                   ' plantillas de cotizacion, y habilita las opciones de seccion'
                   ' "Ocultar precios" / "Ocultar composicion" en el editor de plantillas.'
                   ' Los valores definidos en la plantilla se aplican (y mantienen) en la'
                   ' orden de venta al seleccionarla.',
    'author': 'Sotomayor Consulting International',
    'website': 'https://www.sotomayorconsulting.com',
    'category': 'Sales/Sales',
    'version': '19.0.1.0.0',
    'license': 'LGPL-3',
    'depends': ['sale_management'],
    'data': [
        'views/sale_order_template_views.xml',
    ],
    'installable': True,
    'application': False,
}
