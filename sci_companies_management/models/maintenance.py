from odoo import models, fields

class EntityMaintenance(models.Model):
    _name = 'sci_companies_management.maintenance'
    _description = 'Mantenimiento de Entidad'

    name = fields.Char(string='Descripción', required=True)
    
    entity_id = fields.Many2one('sci_companies_management.entity', string="Empresa" required=True)
    
    
    # Related fields
    partner_id = fields.Many2one(related='entities_id.partner_id', string='Contacto Relacionado')
    incorporation_state_id = fields.Many2one(related='entities_id.incorporation_state_id', string='Estado')
    country_id = fields.Many2one(related='entities_id.country_id', string='Jurisdicción')
    business_structure_id = fields.Many2one(related='entities_id.business_structure_id', string='Estructura')
    incorporation_date = fields.Date(related='entities_id.incorporation_date', string='Fecha de Formación')
    
    
    
    amount = fields.Float(string='Monto')
    state = fields.Selection([
        ('pending', 'Pendiente'),
        ('paid', 'Pagado'),
        ('cancelled', 'Cancelado')
    ], string='Estado', default='pending')
    notes = fields.Text(string='Notas')
