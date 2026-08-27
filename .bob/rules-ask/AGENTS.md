# AGENTS.md — Modo Ask (documentación y contexto)

This file provides guidance to agents when working with code in this repository.

## Dónde vive cada responsabilidad

| Qué buscar | Dónde está |
|---|---|
| Lógica de comparación texto + DOM | `src/comparator.py` |
| Opcodes de diff char-by-char | `calcular_opcodes_inline()` en `comparator.py` (función **pública**, única función pública no prefijada con `_`) |
| Generación HTML + CSS + JS del reporte | `src/reporter.py` — `_CSS` y `_JS` son constantes de módulo |
| Punto de entrada CLI | `src/main.py::main()` — también registrado como `comparar-cfdis` en `pyproject.toml` |
| Configuración de calidad | `.pylintrc` (línea 100, max-args 7) y `pyproject.toml` |

## Comportamiento no obvio del pipeline

El análisis DOM (`lxml`) **solo se activa si el diff de texto no encontró nada**. Esto significa que si dos XMLs tienen los mismos bytes pero con atributos en distinto orden, el DOM los detectará. Si ya hay diferencias de texto, el DOM se salta completamente. Ver `_comparar_xml_dom` en `comparator.py`.

## `reports/` no se versiona

Los reportes generados están en `.gitignore`. El nombre del archivo incluye timestamp: `reporte_comparacion_YYYYMMDD_HHMMSS.html`.

## Carpetas de XMLs

`erpCFDIs/` y `satCFDIs/` también están en `.gitignore` (datos fiscales sensibles). El programa los busca relativos a la raíz del proyecto, detectada como `os.path.dirname(os.path.dirname(__file__))` desde `src/main.py`.
