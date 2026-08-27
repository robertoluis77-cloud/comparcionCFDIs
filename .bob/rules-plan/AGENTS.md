# AGENTS.md — Modo Plan (arquitectura)

This file provides guidance to agents when working with code in this repository.

## Flujo de datos completo

```
comparar_carpetas(ruta_erp, ruta_sat)
  └─ por cada archivo XML emparejado por nombre:
       _leer_archivo()              → (str_contenido, List[str_lineas])
       _comparar_texto()            → (List[DiferenciaDetalle], List[Tuple opcodes])
       _comparar_xml_dom()          → List[DiferenciaDetalle] (solo si texto no encontró nada)
         └─ _comparar_nodos()       → recursivo, produce DiferenciaDetalle sin opcodes_inline
       calcular_opcodes_inline()    → List[Tuple] (dentro de _construir_diferencia_texto)
       → ResultadoArchivo(diferencias, lineas_erp, lineas_sat, opcodes_diff)

generar_reporte_html(ResultadoComparacion, carpeta_reportes)
  └─ por cada ResultadoArchivo DIFERENTE:
       _generar_diff_html()         → usa opcodes_diff (nivel línea) → tabla lado a lado
         └─ _celdas_diff_fila()     → llama calcular_opcodes_inline() OTRA VEZ (inline)
       _generar_tabla_diferencias() → usa opcodes_inline de DiferenciaDetalle (precalculado)
         └─ _fila_tabla_diferencia() → _resaltar_inline(texto, opcodes, lado)
```

## Duplicación intencional de opcodes

`opcodes_inline` se calcula **dos veces** para el mismo par de líneas:
1. En `comparator.py` → almacenado en `DiferenciaDetalle.opcodes_inline` → usado en la **tabla de diferencias** del reporte.
2. En `reporter.py::_celdas_diff_fila()` → calculado al vuelo → usado en la **vista diff lado a lado**.

Esto es deliberado: la vista diff lado a lado trabaja sobre el texto raw de las líneas (con saltos de línea), mientras que la tabla trabaja sobre el contenido ya recortado almacenado en `DiferenciaDetalle`. No unifiques ambas rutas sin verificar que el texto base sea idéntico.

## Restricción arquitectural: los módulos de `src/` no se importan como paquete

El proyecto **no se instala como paquete** para su uso normal; se ejecuta con `python src/main.py`. El entry point del `pyproject.toml` (`comparar-cfdis`) es un bonus para cuando se instala con `pip install -e .`. Si refactorizas imports asumiendo instalación de paquete, romperás la ejecución directa.

## Límites de complejidad y cómo se han resuelto históricamente

- Funciones largas en `reporter.py` se han partido en: `_fila_diff_igual`, `_fila_diff_cambio`, `_celdas_diff_fila`, `_fila_tabla_diferencia`, `_generar_tarjetas`, `_construir_cuerpo_html`. El patrón es siempre extraer la **construcción de un fragmento HTML** a su propia función.
- Funciones largas en `comparator.py` se han partido en: `_comparar_atributos_nodo`, `_construir_diferencia_texto`, `_imprimir_cabecera`, `_imprimir_resumen`, `_procesar_archivo`. El patrón es separar la **lógica de cómputo** de la **lógica de impresión**.
