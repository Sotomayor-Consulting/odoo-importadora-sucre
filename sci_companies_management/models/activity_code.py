from odoo import models, fields

class ActivityCodes(models.Model):
    _name = 'sci_companies_management.activity.code'
    _description = 'Códigos de actividad'

    name = fields.Char(required=True, string="Descripción")
    code = fields.Char(required=True, string="Código")
    
    
class ActivityCategories(models.Model):
    _name='sci_companies_management.activity.category'
    _description = 'Categorias de actividad'
    
    name = fields.Char(required=True, string="Descripción")
    code = fields.Char(required=True, string='Codigo')