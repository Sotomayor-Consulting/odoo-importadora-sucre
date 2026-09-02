# Part of Odoo. See LICENSE file for full copyright and licensing details.

# API base URL for Payphone
API_URL = 'https://pay.payphonetodoesposible.com/api'

# Controller routes
RETURN_URL = '/payphone/return'
CANCEL_URL = '/payphone/cancel'

# Default payment method codes enabled for Payphone
DEFAULT_PAYMENT_METHOD_CODES = {
    'card',
}

# Mapping of Payphone statusCode to Odoo transaction states
# See: https://docs.payphone.app/boton-de-pago-por-redireccion
PAYMENT_STATUS_MAPPING = {
    'done': {3},       # Approved
    'canceled': {2},   # Canceled / Rejected
}
