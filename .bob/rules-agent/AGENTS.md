# AGENTS.md — Modo Agent (codificación)

This file provides guidance to agents when working with code in this repository.

## Patrón de imports — obligatorio en todos los módulos de `src/`

Cada módulo de `src/` debe auto-inyectarse al sys.path **antes** de sus imports locales:

```python
# En reporter.py y cualquier módulo nuevo:
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from comparator import (  # pylint: disable=wrong-import-position
    ...
)
```

En `main.py` el patrón es diferente: una función `_configurar_ruta()` se llama a nivel de módulo (línea 28) antes del bloque de imports. Nuevos módulos deben seguir el patrón de `reporter.py`, no el de `main.py`.

## Pylint — supresiones requeridas (no negociables)

```python
from lxml import etree  # pylint: disable=c-extension-no-member

try:  # pylint: disable=c-extension-no-member
    raiz = etree.fromstring(...)
except etree.XMLSyntaxError as exc:  # pylint: disable=c-extension-no-member
```

El `.pylintrc` tiene `extension-pkg-allow-list=lxml` pero no es suficiente — los comentarios inline siguen siendo necesarios en los puntos de uso.

## Límites de Pylint que requieren refactoring preventivo

- `max-args=7` y `max-positional-arguments=7`: si una función necesita más argumentos, agrupa en dataclass o pasa un objeto existente.
- `too-many-locals`: si superas 15 variables locales, extrae subfunciones auxiliares (ver cómo se hizo con `_generar_tarjetas` y `_construir_cuerpo_html` en `reporter.py`).
- `too-many-branches`: si superas 12 ramas, extrae helpers (ver `_fila_diff_igual` / `_fila_diff_cambio` / `_celdas_diff_fila`).

## `DiferenciaDetalle` — instanciación según contexto

Las instancias para casos "ausente" (sin contraparte) **no incluyen** `opcodes_inline`:
```python
DiferenciaDetalle(numero_linea_erp=None, numero_linea_sat=..., contenido_erp="<ausente>", ...)
# opcodes_inline queda en [] por el field(default_factory=list)
```
Las instancias con ambos lados **sí deben calcularlo**:
```python
DiferenciaDetalle(..., opcodes_inline=calcular_opcodes_inline(linea_erp, linea_sat))
```
`_resaltar_inline` en `reporter.py` maneja ambos casos: lista vacía → solo `html.escape`.

## HTML generado — `_CSS` y `_JS` son constantes de módulo privadas

No son variables locales dentro de ninguna función. Se concatenan como strings en `_construir_cuerpo_html`. Si necesitas añadir estilos, edita las constantes `_CSS` y `_JS` al final del bloque de constantes en `reporter.py` (líneas ~437–565).

## Codificación del contenido del reporte

`etree.fromstring` recibe `contenido.encode("utf-8")` aunque el archivo original sea ISO-8859-1, porque `_leer_archivo` ya decodificó el string a Unicode antes de pasarlo.
