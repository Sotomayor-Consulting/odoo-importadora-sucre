from odoo import models, fields

class EntityFincenReport(models.Model):
    _name = 'sci_companies_management.fincen.report'
    _description = 'Reporte de Fincen'

    name = fields.Char(string='Nombre del reporte', required=True)
    entity_id = fields.Many2one('sci_companies_management.entity', string='Empresa')
    status = fields.Selection([('draft', 'Borrador')])
    filing_date = fields.Date(string='Fecha de emisión')
    expiration_date = fields.Date(string='Fecha de expiración')
    is_exempt = fields.Boolean(string='Exento')
    exemption_reason = fields.Selection([('other','Otro')])
    notes = fields.Text(string="Notas")
    
    fincen_receipt = fields.Binary()
    fincen_receipt_name = fields.Char()
    