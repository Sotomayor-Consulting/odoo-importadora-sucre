"""Migracion 19.0.1.2.0:

El campo `commission.rate.rule.company_id` dejo de ser `related='team_id.company_id'`.
Las reglas existentes tienen `company_id` set automaticamente por el related viejo,
lo cual filtra incorrectamente cuando el equipo opera en varias empresas
(member_company_ids).

Se limpian todas las reglas para que pasen a "multi-cia" (company_id IS NULL).
Si el usuario quiere restringir una regla a una compania especifica, lo asigna
manualmente desde la UI.
"""

import logging

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    if not version:
        return
    cr.execute("""
        UPDATE commission_rate_rule
           SET company_id = NULL
         WHERE company_id IS NOT NULL
    """)
    count = cr.rowcount
    _logger.info(
        'Migracion 19.0.1.2.0: %d reglas pasaron a company_id=NULL (multi-cia).',
        count,
    )
