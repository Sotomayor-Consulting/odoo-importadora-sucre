# Tablero de Existencias — Importadora Sucre

Tablero de hoja de calculo (`spreadsheet.dashboard`) que implementa el *Reporte de existencias*
del diseno `Diseno reporte Importadora Sucre.xlsx`. Aparece en **Tableros / Logistica / Existencias**
para usuarios con el grupo *Inventario / Administrador*.

Una sola hoja con tres secciones apiladas y dos filtros globales: **Periodo** (por defecto, este mes) y **Producto**.
El de producto aplica a las tres secciones; el de periodo solo a Ingresos y Salidas.

Cada seccion muestra su total: el pivote de Existencias trae el suyo al pie, e Ingresos y Salidas
llevan una linea **Total del periodo** encima de la cabecera (al pie quedaria al final del bloque
reservado, decenas de filas por debajo del ultimo dato).

* **1. Existencias** — pivote sobre `stock.quant` (ubicaciones internas). Saldo **actual**; el filtro
  de periodo no le aplica.
* **2. Ingresos** — lista sobre `imp.stock.inflow.report`, vista SQL de este modulo: producto,
  documento (`SP/STOR/...`, `SP/PROD/...`), origen (Compra / Produccion / Devolucion de cliente), proveedor, orden de
  compra, fecha y cantidad. Incluye recepciones de compra **y el producto terminado de las
  ordenes de produccion**; la materia prima consumida por la orden no es un ingreso y se excluye.
  Tampoco cuentan las ordenes de produccion que luego fueron **desensambladas** (`mrp.unbuild`):
  su producto no quedo en bodega.
* **3. Salidas** — lista sobre `imp.stock.outflow.report`, la vista SQL de este modulo: producto,
  orden de entrega, orden de venta, cliente, factura, fecha, cantidad y total.

## Limitaciones conocidas

* `shortcut: la seccion 1 muestra existencias actuales, no a una fecha pasada. Para existencias
  historicas habria que apoyarse en report.stock.quantity, que solo cubre ~3 meses atras y 3
  adelante, y exige un filtro de un unico dia (un rango sumaria saldos diarios).`
* `shortcut: una orden desensamblada se excluye entera, aunque el desensamblaje haya sido
  parcial. Hoy en la base los tres desensamblajes son totales; si aparecen parciales, hay que
  restar la cantidad desensamblada en vez de descartar la fila.`
* Los bloques son de alto fijo porque el tablero no dibuja pestanas de hoja y las secciones van
  apiladas: 40 productos en Existencias, 40 filas en Ingresos y 150 en Salidas. Si un periodo las
  supera, ajustar las constantes en `tools/gen_dashboard.py` y regenerar.
* Las formulas usan coma como separador de argumentos: el motor del tablero no respeta el `;` del
  locale es_419 y devuelve `#BAD_EXPR`.

## Ingresos menos salidas no da las existencias

Es intencional. Las dos listas muestran compras, produccion, devoluciones y entregas; **no**
muestran los ajustes de inventario ni los desensamblajes, que tambien mueven stock. La seccion 1
sale directo de `stock.quant`, que es el saldo real: esa es la cifra a mirar.

## Regenerar el JSON del tablero

`data/files/existencias_dashboard.json` se genera con `python tools/gen_dashboard.py`. Si el
tablero se edita desde la UI, exportar de nuevo el JSON antes de commitear, o los cambios solo
viven en esa base.
