# Sotomayor Consulting International

Repositorio de modulos personalizados de Odoo

## Fases de migración

Se debe reemplazar las personalizaciones de Odoo Studio por un módulo a medida

### Etapas

* Migración: Se migrará la base de datos actual
* Limpieza: Identificar acciones de servidores y personalizaciones realizadas, pero conservando la información de los módulos base.
* Desarrollo del módulo
* Migración de datos: Extracción e importación de datos
* Pruebas
* Despliegue

#### Desarrollo de modulo
##### Registro empresas

| entities_registration    |           |
|--------------------------|-----------|
| **Campo**                | **Tipo**  |
| name                     | char      |
| access_token             | char      |
| _activity_id_            | many2one  |
| _documents_id_           | many2many |
| _partner_id_             | many2one  |
| business_structure       | selection |
| identification_number    | char      |
| _direction_ids_          | many2many |
| _incorporation_state_id_ | many2one  |
| _country_id_             | many2one  |
| state                    | selection |
| resident_agent           | one2many  |
| email_irs                | char      |
| company_service          | char      |
| taxation_type            | selection |
| accounting_method        | selection |
| administration_method    | selection |
| incorporation_date       | date      |
| _member_ids_             | one2many  |
| members_privacy          | selection |
| manager_privacy          | selection |
| signature                | html      |
| _maintenance_fee_ids_    | one2many  |
| _maintenance_ids_        | one2many  |
