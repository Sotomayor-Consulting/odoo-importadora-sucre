# from odoo import http


# class PaymentStripeFee(http.Controller):
#     @http.route('/payment_stripe_fee/payment_stripe_fee', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/payment_stripe_fee/payment_stripe_fee/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('payment_stripe_fee.listing', {
#             'root': '/payment_stripe_fee/payment_stripe_fee',
#             'objects': http.request.env['payment_stripe_fee.payment_stripe_fee'].search([]),
#         })

#     @http.route('/payment_stripe_fee/payment_stripe_fee/objects/<model("payment_stripe_fee.payment_stripe_fee"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('payment_stripe_fee.object', {
#             'object': obj
#         })

