# from odoo import http


# class RegistroEmpresas(http.Controller):
#     @http.route('/sci_companies_management/sci_companies_management', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/sci_companies_management/sci_companies_management/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('sci_companies_management.listing', {
#             'root': '/sci_companies_management/sci_companies_management',
#             'objects': http.request.env['sci_companies_management.sci_companies_management'].search([]),
#         })

#     @http.route('/sci_companies_management/sci_companies_management/objects/<model("sci_companies_management.sci_companies_management"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('sci_companies_management.object', {
#             'object': obj
#         })

