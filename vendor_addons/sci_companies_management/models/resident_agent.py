from odoo import models, fields

class EntityResidentAgent(models.Model):
    _name = 'sci_companies_management.resident.agent'
    _description = 'Lista de Agentes Residentes'

    name = fields.Char(string='Nombre del Agente', required=True)
    partner_id = fields.Many2one('res.partner', string='Contacto relacionado')
    is_agency = fields.Boolean(string='Es una agencia')
    active = fields.Boolean(string='Activo')
    
    is_our_company = fields.Boolean(string="SCI es Agente Residente")
    email = fields.Char(string='Correo Electrónico')
    website = fields.Char(string='Sitio Web')
    phone = fields.Char(string='Teléfono')
    price = fields.Float(string='Precio')

class EntityResidentAgentHistory(models.Model):
    _name = 'sci_companies_management.resident.agent.history'
    _description = 'Agente Residente de la Entidad'

    is_active = fields.Boolean(string='Es el Agente Actual', default=True)
    entity_id = fields.Many2one('sci_companies_management.entity', string='Entidad', required=True, ondelete='cascade')
    agent_id = fields.Many2one('sci_companies_management.resident.agent', string='Agente Residente', required=True)

    # Fechas de agente residente
    start_date = fields.Date(string='Fecha de Inicio', default=fields.Date.context_today)
    end_date = fields.Date(string='Fecha de Fin')

    # Dirección agente residente
    street = fields.Char(string='Calle')
    street2 = fields.Char(string='Calle 2')
    city = fields.Char(string='Ciudad')
    state_id = fields.Many2one('res.country.state', string='Estado')
    country_id = fields.Many2one('res.country', string='País')
    zip = fields.Char(string='C.P.')