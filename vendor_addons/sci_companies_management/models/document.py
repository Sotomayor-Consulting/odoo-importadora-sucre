from odoo import models, fields, api
from odoo.tools import mimetypes as odoo_mimetypes
import base64
import binascii
import mimetypes as py_mimetypes
from markupsafe import Markup

class EntityDocuments(models.Model):
    _name = 'sci_companies_management.document'
    _description = 'Documentos de la Entidad'

    # entity_id = fields.Many2one('sci_companies_management.entity', string='Empresa')
    res_model = fields.Char(string="Modelo relacionado")
    res_id = fields.Integer(string="Id relacionado")
    
    member_id = fields.Many2one('sci_companies_management.member', string='Miembro')
    entity_id = fields.Many2one('sci_companies_management.entity', string='Empresa')
    
    file = fields.Binary(string='Archivo')
    file_name = fields.Char(string='Nombre del archivo')
    mimetype = fields.Char(
        string="Tipo MIME",
        compute="_compute_mimetype",
        store=True,
    )
    preview_html = fields.Html(
        string="Vista previa",
        compute="_compute_preview_html",
        sanitize=False,
    )
    
    issue_date = fields.Date(string='Fecha de emisión')
    expiration_date = fields.Date(string='Fecha de expiración')
    is_expired = fields.Boolean(
        string="Expirado",
        compute="_compute_is_expired",
        store=True
    )
    
    status = fields.Selection([
        ('valid', 'Válido'),
        ('invalid', 'Inválido'),
        ('pending', 'Pendiente')
    ])
    
    document_type_id = fields.Many2one('sci_companies_management.document.type', string='Tipo de documento')
    
    uploaded_by = fields.Many2one(
        'res.users', 
        string='Subido por', 
        default=lambda self: self.env.user
    )
    
    # Aprobación
    approved_by = fields.Many2one('res.users', string='Aprobado por')
    approval_date = fields.Date(string='Fecha de aprobación')
    is_approved = fields.Boolean(string='Aprobado')
    
    version = fields.Integer(default=1)
    is_latest = fields.Boolean(default=True)
    previous_document_id = fields.Many2one('sci_companies_management.document', string='Documento anterior')
    tag_ids = fields.Many2many('sci_companies_management.document.tag', relation='scm_document_tag_rel', string='Etiquetas')
    
    
    country_id = fields.Many2one('res.country', string='País')
    is_confidential = fields.Boolean(string='Confidencial')
    
    notes = fields.Text(string='Notas internas')

    @api.depends('file', 'file_name')
    def _compute_mimetype(self):
        for record in self:
            if record.file:
                mimetype = None
                try:
                    bin_data = base64.b64decode(record.file)
                    mimetype = odoo_mimetypes.guess_mimetype(bin_data)
                except binascii.Error:
                    mimetype = None
                if not mimetype and record.file_name:
                    mimetype = py_mimetypes.guess_type(record.file_name)[0]
                record.mimetype = mimetype or "application/octet-stream"
            else:
                record.mimetype = False

    @api.depends('mimetype', 'file', 'file_name')
    def _compute_preview_html(self):
        for record in self:
            if not record.id or not record.file:
                record.preview_html = False
                continue

            icon_class = record._get_mimetype_icon_class()
            url = (
                "/web/content?"
                f"model=sci_companies_management.document&id={record.id}&field=file"
                f"&filename_field=file_name&download=false"
            )
            title = record.file_name or "Vista previa"
            record.preview_html = Markup(
                f'<a href="{url}" target="_blank" title="{title}">'
                f'<i class="fa {icon_class} fa-lg" />'
                '</a>'
            )

    def _get_mimetype_icon_class(self):
        self.ensure_one()
        mimetype = (self.mimetype or '').lower()
        if mimetype.startswith('image/'):
            return 'fa-file-image-o'
        if 'pdf' in mimetype:
            return 'fa-file-pdf-o'
        if 'word' in mimetype or 'document' in mimetype:
            return 'fa-file-word-o'
        if 'excel' in mimetype or 'spreadsheet' in mimetype or 'sheet' in mimetype or 'csv' in mimetype:
            return 'fa-file-excel-o'
        if 'powerpoint' in mimetype or 'presentation' in mimetype:
            return 'fa-file-powerpoint-o'
        if 'zip' in mimetype or 'compressed' in mimetype:
            return 'fa-file-archive-o'
        if mimetype.startswith('text/'):
            return 'fa-file-text-o'
        return 'fa-file-o'
            
    @api.depends('expiration_date')
    def _compute_is_expired(self):
        today = fields.Date.today()
        for record in self:
            record.is_expired = bool(record.expiration_date and record.expiration_date < today)

    @api.onchange('entity_id', 'member_id')
    def _onchange_related_record(self):
        for record in self:
            record._sync_related_fields()

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            self._prepare_related_vals(vals)
        return super().create(vals_list)

    def write(self, vals):
        result = super().write(vals)
        if 'entity_id' in vals or 'member_id' in vals:
            self._sync_related_fields()
        return result

    @api.model
    def _prepare_related_vals(self, vals):
        if vals.get('entity_id'):
            vals['res_model'] = 'sci_companies_management.entity'
            vals['res_id'] = vals['entity_id']
        elif vals.get('member_id'):
            vals['res_model'] = 'sci_companies_management.member'
            vals['res_id'] = vals['member_id']

    def _sync_related_fields(self):
        for record in self:
            if record.entity_id:
                record.res_model = 'sci_companies_management.entity'
                record.res_id = record.entity_id.id
            elif record.member_id:
                record.res_model = 'sci_companies_management.member'
                record.res_id = record.member_id.id
            else:
                record.res_model = False
                record.res_id = False
            
    # Para versionar documentos       
    # @api.model
    # def create(self, vals):
    #     # Si existe documento previo del mismo tipo → versionar
    #     domain = [
    #         ('document_type_id', '=', vals.get('document_type_id')),
    #         ('res_model', '=', vals.get('res_model')),
    #         ('res_id', '=', vals.get('res_id')),
    #         ('is_latest', '=', True)
    #     ]

    #     previous = self.search(domain, limit=1)

    #     if previous:
    #         previous.is_latest = False
    #         vals['version'] = previous.version + 1
    #         vals['previous_document_id'] = previous.id

    #     return super().create(vals)

 
class EntityDocumentTypes(models.Model):
    _name = 'sci_companies_management.document.type'
    _description = 'Tipos de documentos'

    # Detalles general
    name = fields.Char(string='Nombre', required=True)
    code = fields.Char(string='Código', required=True)
    active = fields.Boolean(string='Activo', default=True) 
    icon = fields.Char(string='Icono')
    
    # Alcance
    target_model = fields.Selection([('member', 'Miembro'), ('entity', 'Empresa')], string="Objetivo")
    
    # Reglas
    is_required = fields.Boolean(string='Requerido', default=True)
    requires_expiration = fields.Boolean(string="Requiere expiración")
    requires_aprobation = fields.Boolean(string="Requiere aprobación")
    
    category = fields.Selection([
        ('kyc', 'KYC'),
        ('tax', 'Fiscal'),
        ('legal', 'Legal'),
        ('bank', 'Bancario'),
        ('corporate', 'Corporativo')
    ], string="Categoría")
    
    # Validaciones
    allowed_extensiones = fields.Char(string="Extensiones permitidas")
    max_file_size = fields.Integer(string="Tamaño máximo (MB) permitido")
    
class EntityDocumentTags(models.Model):
    _name = 'sci_companies_management.document.tag'
    _description = 'Etiquetas de documentos'

    name = fields.Char(string='Nombre', required=True)
    color = fields.Integer(string='Color')
