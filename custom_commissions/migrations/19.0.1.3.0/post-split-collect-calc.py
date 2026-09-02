"""Migracion 19.0.1.3.0:

Se separa el flujo en dos fases:
  - action_collect_data (obtener datos sin aplicar reglas) -> state 'collected'
  - action_calculate (aplicar reglas) -> state 'calculated'

Se anade el campo `commission.sheet.data_source` (parametro de obtencion).

Se anade `commission.detail.line.event_type` (que evento creo la linea).

- Hojas en 'draft' / 'calculated' / 'approved' / 'paid' conservan estado.
- Las hojas existentes que ya estaban 'calculated' se quedan asi y se les
  setea data_source = 'bank_paid' por compatibilidad (era el unico modo
  implementado antes).
- Detail lines existentes se les fija event_type segun rule_type si tenian
  regla, o NULL si no. Si tenian commission_amount > 0 quedan como
  is_calculated=True via el compute.

Es seguro re-ejecutar.
"""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return

    # 1. Default data_source = 'bank_paid' en hojas que no lo tengan
    #    (columna ya existe por la nueva version del manifest).
    cr.execute("""
        UPDATE commission_sheet
           SET data_source = 'bank_paid'
         WHERE data_source IS NULL
    """)
    _logger.info(
        'Migracion 19.0.1.3.0: %d hojas con data_source=bank_paid por default.',
        cr.rowcount,
    )

    # 2. event_type por copia de rule_type donde haya regla aplicada.
    cr.execute("""
        UPDATE commission_detail_line dl
           SET event_type = r.rule_type
          FROM commission_rate_rule r
         WHERE dl.rule_id = r.id
           AND dl.event_type IS NULL
    """)
    _logger.info(
        'Migracion 19.0.1.3.0: %d detail lines con event_type copiado de regla.',
        cr.rowcount,
    )

    # 3. Detail lines con source='manual' -> event_type='manual'.
    cr.execute("""
        UPDATE commission_detail_line
           SET event_type = 'manual'
         WHERE source = 'manual' AND event_type IS NULL
    """)
    _logger.info(
        'Migracion 19.0.1.3.0: %d detail lines manuales actualizadas.',
        cr.rowcount,
    )
