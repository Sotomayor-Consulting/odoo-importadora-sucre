from odoo import models, fields, api
from odoo.exceptions import ValidationError


class EntityMembers(models.Model):
    _name = 'sci_companies_management.member'
    _description = 'Miembros de la Entidad'
    
    # Contacto relacionado
    partner_id = fields.Many2one('res.partner', string='Contacto relacionado')

    # Relación entre empresas
    is_entity = fields.Boolean(string='Es una empresa interna')
    internal_entity_id = fields.Many2one('sci_companies_management.entity', string='Empresa')
    internal_member = fields.Boolean(string='Es un miembro interno')
    
    # Información personal de miembro
    first_name = fields.Char(string='Nombres')
    last_name = fields.Char(string='Apellidos')
    name = fields.Char(string="Nombre")
    full_name = fields.Char(
        string='Nombre Completo',
        compute="_compute_full_name",
        store=True,
    )
    birth_date = fields.Date(string="Fecha de Nacimiento")
    person_type = fields.Selection([
        ('individual', 'Individuo'),
        ('company', 'Persona Jurídica')
    ])
    country_nationality_id = fields.Many2one('res.country', string='País de nacionalidad')
    id_issuing_country_id = fields.Many2one('res.country', string='País de emisión de identificación')
    id_issuing_state_id = fields.Many2one(
        'res.country.state', 
        string='Estado de emisión de identificación',
        domain="[('country_id', '=', id_issuing_country_id)]"
    )
    marital_status = fields.Selection([
        ('single', 'Soltero/a'),
        ('married', 'Casado/a'),
        ('divorced', 'Divorciado/a'),
        ('widowed', 'Viudo/a'),
        ('other', 'Otro')
    ])
    identification_number = fields.Char(string='Número de Identificación')
    identification_type = fields.Selection([
        ('c.i', 'Cédula de identidad'),
        ('passport', 'Pasaporte'),
        ('nit', 'Número de identificación tributaria'),
        ('ein', 'EIN'),
        ('other', 'Otro')
    ])
    ssn = fields.Char(string='Número de Seguro Social')
    itin = fields.Char(string='Número de Identificación Tributaria')
    document_ids = fields.One2many('sci_companies_management.document', 'member_id', string="Documentos de cliente")
    
    
    kyc_status = fields.Selection([
        ('draft', 'Borrador'),
        ('pending', 'Pendiente'),
        ('approved', 'Aprobado'),
        ('rejected', 'Rechazado')
    ], default='draft')
    
    is_pep = fields.Boolean(string="PEP")
    tax_residency_country = fields.Many2one('res.country', string='País de residencia fiscal')

    address_ids = fields.One2many(
        'sci_companies_management.address', 'member_id', string='Direcciones'
    )
    date_start = fields.Date(string='Fecha de inicio')
    date_end = fields.Date(string='Fecha de fin')

    @api.depends('first_name', 'last_name')
    def _compute_full_name(self):
        for record in self:
            record.full_name = f"{record.first_name or ''} {record.last_name or ''}".strip()

    @api.depends('name','first_name', 'last_name', 'person_type')
    def _compute_display_name(self):
        for record in self:
            if record.person_type == 'individual':
                record.display_name = record.full_name or ''
            else:
                record.display_name = record.name or ''
                
    @api.constrains('person_type', 'first_name', 'last_name', 'name')
    def _check_required_names(self):
        for record in self:
            if record.person_type == 'individual':
                if not record.first_name or not record.last_name:
                    raise ValidationError("Ingrese los nombres y apellidos del miembro")
            elif record.person_type == 'company':
                if not record.name:
                    raise ValidationError("Ingrese el nombre de la entidad")
                
