from odoo import models, fields, api
from odoo.exceptions import ValidationError

class EntitiesRegistration(models.Model):
    _name = "sci_companies_management.entity"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _description = "Entidad Legal"

    # Acceso a vista pública
    access_token = fields.Char(help="Token de acceso para vista pública de la entidad")
    # Detalles generales de empresa
    name = fields.Char(required=True, string="Nombre de empresa")
    identification_number = fields.Char(help="Número de identificación fiscal de la entidad (EIN, ITIN, etc.)")
    contact_id = fields.Many2one("res.partner", string="Persona de contacto",
        help="Persona física que representa a la entidad (gerente, representante legal, etc.)")
    business_structure_id = fields.Many2one("sci_companies_management.business.structure",
        help="Tipo de estructura legal (LLC, LP, Corporation, etc.)")
    document_ids = fields.One2many(
        "sci_companies_management.document", "entity_id", string="Documentos"
    )
    address_ids = fields.One2many(
        "sci_companies_management.address", "entity_id", string="Direcciones"
    )
    country_id = fields.Many2one("res.country", help="País de jurisdicción donde se constituyó la entidad")
    incorporation_state_id = fields.Many2one("res.country.state",
        help="Estado de EE.UU. donde se registró la entidad")
    status = fields.Selection(
        [("draft", "Borrador"), ("registered", "Registrado"), ("active", "Activo"), ("dissolved", "Disuelto")],
        default='draft',
        string="Estado",
        help="Estado actual de la entidad"
    )
    resident_agent_history_ids = fields.One2many(
        "sci_companies_management.resident.agent.history", "entity_id"
    )
    email_irs = fields.Char(string="Correo electrónico IRS",
        help="Correo electrónico registrado ante el IRS para comunicaciones oficiales")
    company_service = fields.Char(string="Actividad/Servicio")
    # Detalles de actividad de la empresa
    activity_id = fields.Many2one("sci_companies_management.activity.code", string="Código de Actividad",
        help="Código NAICS o de actividad económica principal")
    service = fields.Char(string="Servicio/Producto",
        help="Descripción corta del servicio o producto que ofrece la entidad")
    service_description = fields.Text(string="Descripción de actividades",
        help="Descripción detallada de las actividades comerciales de la entidad")
    us_source_income = fields.Boolean(string="Ingresos de Fuente Americana",
        help="Indica si la entidad genera ingresos de fuente americana (EE.UU.)")
    # Información cumplimiento
    taxation_type = fields.Selection(
        [
            ("disregarded", "Disregarded Entity"),
            ("corporation", "Corporation"),
        ],
        help="Tipo de tributación IRS: Disregarded Entity (ignorada, ej: LLC unipersonal) o Corporation (tributa como corporación)"
    )
    accounting_method = fields.Selection(
        [("cash", "Efectivo"), ("accrual", "Devengado")],
        help="Método contable: Efectivo (Cash) o Devengado (Accrual)"
    )
    # Estructura de empresa
    administration_method = fields.Selection(
        [("member_managed", "Member Managed"), ("manager_managed", "Manager Managed")],
        help="Método de administración: Member-managed (todos los miembros administran) o Manager-managed (gerentes designados)"
    )
    incorporation_date = fields.Date(string="Fecha de formación",
        help="Fecha de constitución o registro de la entidad")
    member_line_ids = fields.One2many("sci_companies_management.member.line", "entity_id")
    members_privacy = fields.Selection([("public", "Público"), ("private", "Privado")],
        help="Confidencialidad de los miembros: Público (visible en registros estatales) o Privado")
    manager_privacy = fields.Selection([("public", "Público"), ("private", "Privado")],
        help="Confidencialidad de los gerentes: Público o Privado")
    joint_ownership = fields.Boolean(string="Joint Ownership",
        help="Indica si la propiedad es conjunta (Joint Ownership)")
    # Cumplimiento FinCEN
    report_fincen_ids = fields.One2many("sci_companies_management.fincen.report", "entity_id")
    # Firma de cliente
    signature = fields.Binary()
    # Opciones de mantenimiento anual
    partner_id = fields.Many2one('res.partner', string='Empresa Vinculada',
        help="Registro de la empresa en Contactos (res.partner). Se usa en facturación, órdenes de venta y CRM.")
    billing_partner_id = fields.Many2one('res.partner', string="Contacto para facturación", store=True, compute="_compute_billing_partner", readonly=False,
        help="Contacto al que se envían las facturas. Si está vacío, se usa la Empresa Vinculada.")
    # maintenance_fee_ids = fields.One2many('entities.maintenance.fee', 'registration_id')
    # maintenance_ids = fields.One2many('entities.maintenance', 'registration_id')
    
    @api.onchange('contact_id')
    def _onchange_contact_id(self):
        for record in self:
            if record.contact_id:
                record.email_irs = record.contact_id.email

    @api.onchange('business_structure_id')
    def _onchange_business_structure(self):
        if self.business_structure_id:
            valid_roles = self.business_structure_id.role_ids
            for line in self.member_line_ids:
                invalid_roles = line.role_ids - valid_roles
                if invalid_roles:
                    return {
                        'warning': {
                            'title': 'Roles inválidos',
                            'message': (
                                f"Cambió la estructura a '{self.business_structure_id.name}'. "
                                "Algunos roles asignados ya no son válidos para esta estructura. "
                                "Revise las líneas de miembros."
                            ),
                        }
                    }

    @api.depends('partner_id')
    def _compute_billing_partner(self):
        for r in self:
            if r.partner_id and not r.billing_partner_id:
                r.billing_partner_id = r.partner_id
                
    # Creación de direcciones
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            addresses = vals.get('address_ids', [])
            addresses.extend([
                (0, 0, {'address_type': 'physical'}),
                (0, 0, {'address_type': 'irs'}),
                (0, 0, {'address_type': 'agent'})
            ])
            vals['address_ids'] = addresses
            
        return super().create(vals_list)
    
    @api.constrains('address_ids')
    def _check_unique_address_types(self):
        for record in self:
            # Extraemos los tipos de las líneas del One2many (sci_companies_management.address)
            # Ignoramos los que no tienen tipo asignado o los que son de tipo 'other'
            types_found = [
                address.address_type 
                for address in record.address_ids 
                if address.address_type and address.address_type != 'other'
            ]
            
            # Si al convertir la lista a un set (que elimina duplicados) el tamaño cambia, hay repetidos
            if len(types_found) != len(set(types_found)):
                raise ValidationError("Ya existe registrada una dirección de este tipo, si requiere agregar direcciones adicionales, utilice el tipo 'Otro'")
            
    @api.constrains('member_line_ids')
    def _check_member_lines(self):
        for record in self:
            if len(record.member_line_ids.mapped('member_id')) != len(record.member_line_ids):
                raise ValidationError("Existen miembros duplicados. Asigne todos sus roles (Ej: Miembro, Manager) en una sola línea.")

            ownership_lines = record.member_line_ids.filtered(
                lambda l: any(r.is_ownership_role for r in l.role_ids)
            )
            if ownership_lines and sum(ownership_lines.mapped('percentage')) != 1:
                raise ValidationError("El porcentaje total de los miembros con rol de participación debe ser exactamente 100%.")
            
    @api.ondelete(at_uninstall=False)
    def _check_delete_protection(self):
        for record in self:
            if record.status not in ('draft',):
                raise ValidationError(
                    "Solo se puede eliminar entidades en estado Borrador. "
                    "Elimine las líneas de miembro y establezca como Borrador primero."
                )
            if record.member_line_ids:
                raise ValidationError(
                    "Elimine las líneas de miembro antes de borrar la entidad."
                )

    def action_register(self):
        self._validate_registration()
        self.status = 'registered'

    def action_set_active(self):
        self.status = 'active'

    def action_dissolve(self):
        self.status = 'dissolved'

    def _validate_registration(self):
        for record in self:
            if not record.name:
                raise ValidationError("El nombre de la empresa es obligatorio.")
            if not record.business_structure_id:
                raise ValidationError("La estructura legal es obligatoria.")
            if not record.incorporation_state_id:
                raise ValidationError("El estado de incorporación es obligatorio.")
            if not record.incorporation_date:
                raise ValidationError("La fecha de formación es obligatoria.")

            if not record.member_line_ids:
                raise ValidationError("Debe agregar al menos un miembro a la entidad.")

            valid_roles = record.business_structure_id.role_ids
            for line in record.member_line_ids:
                if not line.role_ids:
                    raise ValidationError(
                        f"El miembro {line.member_id.display_name} debe tener al menos un rol asignado."
                    )
                invalid_roles = line.role_ids - valid_roles
                if invalid_roles:
                    raise ValidationError(
                        f"El rol '{invalid_roles[0].name}' no es válido para la estructura {record.business_structure_id.name}."
                    )

            if record.administration_method == 'manager_managed':
                manager_role = self.env['sci_companies_management.role'].search([('name', '=', 'Manager')], limit=1)
                if manager_role and not record.member_line_ids.filtered(lambda l: manager_role in l.role_ids):
                    raise ValidationError(
                        "La entidad es Manager-Managed pero no tiene ningún Manager asignado."
                    )

            if record.business_structure_id.code == '2':
                gp_role = self.env['sci_companies_management.role'].search([('name', '=', 'General Partner')], limit=1)
                if gp_role and not record.member_line_ids.filtered(lambda l: gp_role in l.role_ids):
                    raise ValidationError(
                        "Una LP debe tener al menos un General Partner asignado."
                    )


class EntityAddressesList(models.Model):
    _name = "sci_companies_management.address"
    _description = "Direcciones"

    entity_id = fields.Many2one("sci_companies_management.entity", string="Empresa")
    member_id = fields.Many2one("sci_companies_management.member", string="Miembro")
    full_address = fields.Char(string="Dirección Completa")
    address_type = fields.Selection(
        [
            ("physical", "Dirección Física"),
            ("mailing", "Dirección Postal"),
            ("agent", "Dirección del Agente Residente"),
            ("other", "Otra Dirección"),
            ("irs", "Dirección registrada ante el IRS"),
        ]
    )
    street = fields.Char(string="Calle")
    street2 = fields.Char(string="Calle 2")
    city = fields.Char(string="Ciudad")
    state_id = fields.Many2one("res.country.state", string="Estado")
    country_id = fields.Many2one("res.country", string="País")
    zip = fields.Char(string="C.P.", change_default=True)

    @api.constrains('entity_id', 'member_id')
    def _check_owner(self):
        for rec in self:
            if not rec.entity_id and not rec.member_id:
                raise ValidationError("La dirección debe pertenecer a una entidad o a un miembro.")

class EntityMemberLine(models.Model):
    _name = "sci_companies_management.member.line"
    _description = "Lineas de participación"

    # Relacion con la entidad
    entity_id = fields.Many2one(
        "sci_companies_management.entity", required=True, string="Empresa"
    )
    business_structure_id = fields.Many2one(
        related="entity_id.business_structure_id", store=True, string="Estructura"
    )
    member_id = fields.Many2one("sci_companies_management.member", required=True, string="Miembro")
    role_ids = fields.Many2many(
        "sci_companies_management.role", relation="member_line_role_rel", string="Roles"
    )
    is_designated_by_us = fields.Boolean(string="Es un miembro/manager interno designado")

    # Acciones o porcentaje de control de socio sobre la entidad
    percentage = fields.Float(string="Porcentaje")
    economic_percentage = fields.Float(string="Porcentaje económico")
    voting_percentage = fields.Float(string="Porcentaje de votación")
    company_shares = fields.Float(string="Acciones de la empresa")
    stock_class = fields.Selection(
        [("common", "Común"), ("preferred", "Preferente")],
        string="Clase de acción",
        default="common",
    )
    participation_type = fields.Selection(
        [
            ("direct", "Titular Directo"),
            ("contingent", "Sustituto"),
            ("proxy", "Apoderado"),
            ("usufruct", "Usufructo"),
            ("joint", "Joint"),
        ],
        default="direct",
        required=True,
    )

    # Relación con otros socios
    is_beneficial_owner = fields.Boolean(string="Es beneficiario")
    parent_line_id = fields.Many2one("sci_companies_management.member.line", string="Socios Padre")
    child_line_ids = fields.One2many(
        "sci_companies_management.member.line", "parent_line_id", string="Socios Hijos"
    )
    # Periodo que tiene control en la entidad
    date_start = fields.Date(string="Desde")
    date_end = fields.Date(string="Hasta")

    # Estado de socio
    active = fields.Boolean(default=True)

    @api.ondelete(at_uninstall=False)
    def _check_member_line_delete(self):
        for line in self:
            if line.entity_id and line.entity_id.status not in ('draft',):
                raise ValidationError(
                    "No puede modificar miembros de una entidad que ya ha sido registrada. "
                    "Establezca la entidad como Borrador primero."
                )

class EntityBusinessStructure(models.Model):
    _name = "sci_companies_management.business.structure"
    _description = "Tipo de estructuras"

    name = fields.Char(required=True)
    code = fields.Char(required=True)
    active = fields.Boolean(default=True)
    role_ids = fields.Many2many(
        "sci_companies_management.role",
        relation="structure_role_rel",
        column1="structure_id",
        column2="role_id",
    )

class EntityRoles(models.Model):
    _name = "sci_companies_management.role"
    _description = "Roles de Miembros"

    name = fields.Char(required=True)
    code = fields.Char(required=True)
    active = fields.Boolean(default=True)
    is_ownership_role = fields.Boolean(
        string="Rol de participación",
        default=True,
        help="Indica si este rol requiere participación accionaria (Member, Limited Partner). "
             "Roles como Manager no tienen porcentaje de participación.",
    )
    structure_ids = fields.Many2many(
        "sci_companies_management.business.structure",
        relation="structure_role_rel",
        column1="role_id",
        column2="structure_id",
    )
