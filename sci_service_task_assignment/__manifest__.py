{
    'name': 'Service Task Assignment',
    'summary': 'Responsable, tiempo estimado y plazo por servicio/categoria al crear la tarea',
    'description': 'Permite configurar, por producto de tipo servicio o por categoria de'
                   ' producto, el responsable (persona o rol), el tiempo estimado y el plazo'
                   ' en dias. Al confirmar la orden de venta y generarse la tarea, esta nace'
                   ' con el asignado, las horas estimadas y la fecha limite (confirmacion +'
                   ' N dias). El servicio prevalece sobre la categoria. No depende de Partes'
                   ' de horas.',
    'author': 'Sotomayor Consulting International',
    'website': 'https://www.sotomayorconsulting.com',
    'category': 'Sales/Sales',
    'version': '19.0.1.0.0',
    'license': 'LGPL-3',
    'depends': ['sale_project'],
    'data': [
        'views/product_views.xml',
        'views/product_category_views.xml',
        'views/project_role_views.xml',
    ],
    'installable': True,
    'application': False,
}
