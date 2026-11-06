"""Genera el JSON del tablero de existencias (formato o-spreadsheet de Odoo 19).

Una sola hoja: el tablero de Odoo solo muestra la primera y no dibuja pestanas.
Las tres secciones van apiladas, con bloques de alto fijo para que no se pisen:
el pivote se limita con el 2do argumento de PIVOT y las listas tienen un numero
fijo de formulas ODOO.LIST.
"""
import io
import json

OUT = r"C:\Proyectos\odoo-importadora-sucre\vendor_addons\imp_sucre_stock_dashboard\data\files\existencias_dashboard.json"

DATE_FILTER = "f1d0e4a2-1111-4a2b-9c3d-000000000001"
PRODUCT_FILTER = "f1d0e4a2-2222-4a2b-9c3d-000000000002"

# El filtro de producto aplica a las tres secciones por el mismo campo.
PRODUCT_MATCH = {PRODUCT_FILTER: {"chain": "product_id", "type": "many2one"}}

# Locale es_419: el separador de argumentos de formula es ';' (decimal = ',').
LOCALE = {
    "name": "Spanish (Latin America) / Espa\u00f1ol (Am\u00e9rica Latina)",
    "code": "es_419",
    "thousandsSeparator": ".",
    "decimalSeparator": ",",
    "dateFormat": "dd/mm/yyyy",
    "timeFormat": "hh:mm:ss",
    "formulaArgSeparator": ";",
    "weekStart": 1,
}

STYLES = {
    "1": {"fontSize": 18, "bold": True, "textColor": "#1f4e5f"},
    "2": {"fontSize": 14, "bold": True, "textColor": "#1f4e5f"},
    "3": {"fontSize": 10, "textColor": "#777777"},
    "4": {"bold": True},
}

COL_SIZES = [300, 140, 110, 220, 170, 120, 90, 110]

# Secciones apiladas: (fila del titulo, filas reservadas para el bloque)
EXIST_TITLE = 3
EXIST_BLOCK = 6          # primera fila del pivote
EXIST_PIVOT_ROWS = 40    # productos como maximo (hoy hay 29 con saldo)

ING_TITLE = EXIST_BLOCK + EXIST_PIVOT_ROWS + 6
ING_HEADER = ING_TITLE + 3
ING_ROWS = 60
# (indice de columna, campo): se saltan columnas para alinear con la seccion 3,
# que comparte los anchos de esta misma hoja.
ING_COLS = [(0, "product_id"), (1, "origin_ref"), (2, "source"), (3, "partner_id"),
            (4, "purchase_order_id"), (5, "date"), (6, "quantity")]
ING_SUM = [6]  # columnas numericas a totalizar

SAL_TITLE = ING_HEADER + ING_ROWS + 4
SAL_HEADER = SAL_TITLE + 3
SAL_ROWS = 150
SAL_COLS = list(enumerate(["product_id", "picking_id", "sale_order_id", "partner_id",
                           "invoice_ref", "date", "quantity", "price_total"]))
SAL_SUM = [6, 7]


def col_letter(i):
    return chr(ord("A") + i)


cells = {
    "A1": "Reporte de existencias",
    "A%d" % EXIST_TITLE: "1. Existencias",
    "A%d" % (EXIST_TITLE + 1): "Saldo a mano por producto. No depende del filtro de periodo.",
    "A%d" % EXIST_BLOCK: "=PIVOT(1,%d)" % EXIST_PIVOT_ROWS,
    "A%d" % ING_TITLE: "2. Ingresos",
    "A%d" % (ING_TITLE + 1): "Recepciones y fabricacion validadas en el periodo.",
    "A%d" % SAL_TITLE: "3. Salidas",
    "A%d" % (SAL_TITLE + 1): "Entregas validadas en el periodo.",
}
styles = {
    "A1": "1",
    "A%d" % EXIST_TITLE: "2", "A%d" % (EXIST_TITLE + 1): "3",
    "A%d" % ING_TITLE: "2", "A%d" % (ING_TITLE + 1): "3",
    "A%d" % SAL_TITLE: "2", "A%d" % (SAL_TITLE + 1): "3",
}

for list_id, header_row, n_rows, columns, sum_cols in (
    ("1", ING_HEADER, ING_ROWS, ING_COLS, ING_SUM),
    ("2", SAL_HEADER, SAL_ROWS, SAL_COLS, SAL_SUM),
):
    for i, field in columns:
        letter = col_letter(i)
        cells["%s%d" % (letter, header_row)] = '=ODOO.LIST.HEADER(%s,"%s")' % (list_id, field)
        for r in range(1, n_rows + 1):
            cells["%s%d" % (letter, header_row + r)] = '=ODOO.LIST(%s,%d,"%s")' % (list_id, r, field)
    # Los totales van ARRIBA de la tabla: al pie quedarian al final del bloque
    # reservado, decenas de filas vacias por debajo del ultimo dato.
    # SUM ignora las celdas vacias de las filas sin datos.
    total_row = header_row - 1
    cells["A%d" % total_row] = "Total del periodo"
    styles["A%d" % total_row] = "4"
    for i in sum_cols:
        letter = col_letter(i)
        cells["%s%d" % (letter, total_row)] = "=SUM(%s%d:%s%d)" % (
            letter, header_row + 1, letter, header_row + n_rows)
        styles["%s%d" % (letter, total_row)] = "4"

ROW_NUMBER = SAL_HEADER + SAL_ROWS + 10

sheet = {
    "id": "existencias",
    "name": "Reporte de existencias",
    "colNumber": len(COL_SIZES),
    "rowNumber": ROW_NUMBER,
    "rows": {},
    "cols": {str(i): {"size": s} for i, s in enumerate(COL_SIZES)},
    "merges": [],
    "cells": cells,
    "styles": styles,
    "formats": {},
    "borders": {},
    "conditionalFormats": [],
    "dataValidationRules": [],
    "figures": [],
    "tables": [],
    "areGridLinesVisible": False,
    "isVisible": True,
    "headerGroups": {},
    "comments": {},
}

data = {
    "version": "18.5.10",
    "sheets": [sheet],
    "styles": STYLES,
    "formats": {},
    "borders": {},
    "revisionId": "START_REVISION",
    "uniqueFigureIds": True,
    "settings": {"locale": LOCALE},
    "pivots": {
        "1": {
            "id": "1",
            "type": "ODOO",
            "model": "stock.quant",
            "name": "Existencias por producto",
            "domain": [["location_id.usage", "=", "internal"]],
            "context": {},
            "sortedColumn": None,
            "rows": [{"fieldName": "product_id"}],
            "columns": [],
            "measures": [{"id": "quantity:sum", "fieldName": "quantity", "aggregator": "sum"}],
            "formulaId": "1",
            # Sin el filtro de periodo: el saldo a mano es el actual, no un rango.
            "fieldMatching": dict(PRODUCT_MATCH),
        },
    },
    "pivotNextId": 2,
    "lists": {
        "1": {
            "id": "1",
            "model": "imp.stock.inflow.report",
            "name": "Ingresos",
            "columns": [f for _i, f in ING_COLS],
            "domain": [],
            "context": {},
            "orderBy": [{"name": "date", "asc": False}],
            "fieldMatching": dict(PRODUCT_MATCH,
                                  **{DATE_FILTER: {"chain": "date", "type": "datetime", "offset": 0}}),
        },
        "2": {
            "id": "2",
            "model": "imp.stock.outflow.report",
            "name": "Salidas",
            "columns": [f for _i, f in SAL_COLS],
            "domain": [],
            "context": {},
            "orderBy": [{"name": "date", "asc": False}],
            "fieldMatching": dict(PRODUCT_MATCH,
                                  **{DATE_FILTER: {"chain": "date", "type": "datetime", "offset": 0}}),
        },
    },
    "listNextId": 3,
    "globalFilters": [
        {
            "id": DATE_FILTER,
            "type": "date",
            "label": "Periodo",
            "defaultValue": "this_month",
        },
        {
            "id": PRODUCT_FILTER,
            "type": "relation",
            "label": "Producto",
            "modelName": "product.product",
            "defaultValueDisplayNames": [],
        },
    ],
    "customTableStyles": {},
    "chartOdooMenusReferences": {},
}

with io.open(OUT, "w", encoding="utf-8", newline="\n") as fh:
    json.dump(data, fh, ensure_ascii=False, indent=1)
    fh.write("\n")
print("escrito", OUT, "filas:", ROW_NUMBER)
