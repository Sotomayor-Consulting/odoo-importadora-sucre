"""Migracion 19.0.1.1.0:

Renombra el modelo `commission.detail.log` a `commission.detail.line` y
ajusta los registros relacionados (ir.model, ir.model.data, ir.model.fields,
tabla SQL y constraints) antes de cargar el manifest. Tambien quita los
campos `commission_basis` y `commission_amount_basis` de `crm.team` que ya
no existen en el modelo.

Se ejecuta como script `pre-*` (antes de cargar manifest/data del modulo),
por lo que el resto del upgrade procede en limpio.
"""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        # Instalacion fresca: no hay nada que migrar.
        return

    # ------------------------------------------------------------------
    # 1. Renombrar la tabla SQL (si existe la vieja y no la nueva).
    # ------------------------------------------------------------------
    cr.execute("""
        SELECT to_regclass('commission_detail_log'),
               to_regclass('commission_detail_line')
    """)
    old_table, new_table = cr.fetchone()
    if old_table and not new_table:
        _logger.info('Renombrando tabla commission_detail_log -> commission_detail_line')
        cr.execute('ALTER TABLE commission_detail_log RENAME TO commission_detail_line')
        # Renombrar tambien las constraints e indices que llevan el prefijo viejo.
        cr.execute("""
            SELECT conname FROM pg_constraint
             WHERE conname LIKE 'commission_detail_log%'
        """)
        for (conname,) in cr.fetchall():
            new_name = conname.replace('commission_detail_log', 'commission_detail_line', 1)
            cr.execute(
                'ALTER TABLE commission_detail_line RENAME CONSTRAINT %s TO %s'
                % (conname, new_name)
            )
        cr.execute("""
            SELECT indexname FROM pg_indexes
             WHERE indexname LIKE 'commission_detail_log%'
        """)
        for (indexname,) in cr.fetchall():
            new_name = indexname.replace('commission_detail_log', 'commission_detail_line', 1)
            cr.execute('ALTER INDEX %s RENAME TO %s' % (indexname, new_name))

    # ------------------------------------------------------------------
    # 2. Renombrar ir.model y sus ir.model.data.
    # ------------------------------------------------------------------
    cr.execute("""
        UPDATE ir_model
           SET model = 'commission.detail.line'
         WHERE model = 'commission.detail.log'
    """)
    cr.execute("""
        UPDATE ir_model_data
           SET name = 'model_commission_detail_line'
         WHERE module = 'custom_commissions'
           AND name = 'model_commission_detail_log'
    """)

    # ------------------------------------------------------------------
    # 3. Renombrar campos del modelo en ir.model.fields.
    # ------------------------------------------------------------------
    cr.execute("""
        UPDATE ir_model_fields
           SET model = 'commission.detail.line'
         WHERE model = 'commission.detail.log'
    """)
    # Y los ir.model.data de cada campo.
    cr.execute("""
        UPDATE ir_model_data
           SET name = replace(name, 'commission_detail_log_', 'commission_detail_line_')
         WHERE module = 'custom_commissions'
           AND model = 'ir.model.fields'
           AND name LIKE 'field_commission_detail_log_%'
    """)

    # ------------------------------------------------------------------
    # 4. Renombrar relacion en ir.model.fields que apuntaban al modelo
    #    como destino de related/many2one.
    # ------------------------------------------------------------------
    cr.execute("""
        UPDATE ir_model_fields
           SET relation = 'commission.detail.line'
         WHERE relation = 'commission.detail.log'
    """)

    # ------------------------------------------------------------------
    # 5. Renombrar el campo One2many en commission.line:
    #    detail_log_ids -> detail_line_ids
    # ------------------------------------------------------------------
    cr.execute("""
        UPDATE ir_model_fields
           SET name = 'detail_line_ids'
         WHERE model = 'commission.line'
           AND name = 'detail_log_ids'
    """)
    cr.execute("""
        UPDATE ir_model_data
           SET name = 'field_commission_line__detail_line_ids'
         WHERE module = 'custom_commissions'
           AND model = 'ir.model.fields'
           AND name = 'field_commission_line__detail_log_ids'
    """)

    # ------------------------------------------------------------------
    # 6. Limpiar ir.model.data huerfanos del security XML viejo.
    #    Las reglas commission_detail_log_*_rule se reemplazan por
    #    commission_detail_line_*_rule al cargar el nuevo XML.
    # ------------------------------------------------------------------
    cr.execute("""
        DELETE FROM ir_rule
         WHERE id IN (
            SELECT res_id FROM ir_model_data
             WHERE module = 'custom_commissions'
               AND model = 'ir.rule'
               AND name IN ('commission_detail_log_user_rule',
                            'commission_detail_log_manager_rule')
         )
    """)
    cr.execute("""
        DELETE FROM ir_model_data
         WHERE module = 'custom_commissions'
           AND model = 'ir.rule'
           AND name IN ('commission_detail_log_user_rule',
                        'commission_detail_log_manager_rule')
    """)

    # ------------------------------------------------------------------
    # 7. Quitar campos eliminados de crm.team: commission_basis,
    #    commission_amount_basis.
    # ------------------------------------------------------------------
    cr.execute("""
        ALTER TABLE crm_team
            DROP COLUMN IF EXISTS commission_basis,
            DROP COLUMN IF EXISTS commission_amount_basis
    """)
    cr.execute("""
        DELETE FROM ir_model_fields
         WHERE model = 'crm.team'
           AND name IN ('commission_basis', 'commission_amount_basis')
    """)
    cr.execute("""
        DELETE FROM ir_model_data
         WHERE module = 'custom_commissions'
           AND model = 'ir.model.fields'
           AND name IN ('field_crm_team__commission_basis',
                        'field_crm_team__commission_amount_basis')
    """)

    # ------------------------------------------------------------------
    # 8. Limpiar entrada vieja en ir.model.access.csv ID.
    # ------------------------------------------------------------------
    cr.execute("""
        DELETE FROM ir_model_data
         WHERE module = 'custom_commissions'
           AND model = 'ir.model.access'
           AND name IN ('access_commission_detail_log_user',
                        'access_commission_detail_log_manager')
    """)

    _logger.info('Migracion 19.0.1.1.0 completada: commission.detail.log -> commission.detail.line')
