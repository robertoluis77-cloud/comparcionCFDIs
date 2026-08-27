# AGENTS.md

This file provides guidance to agents when working with code in this repository.

## Comandos esenciales

```bash
# Ejecutar el programa (desde la raíz del proyecto)
python src/main.py

# Lint — DEBE ejecutarse así; el .pylintrc inyecta src/ al sys.path vía init-hook
python -m pylint src/comparator.py src/reporter.py src/main.py \
  --init-hook="import sys; sys.path.insert(0,'src')"

# Instalar dependencias de runtime
pip install -e .

# Instalar incluyendo herramientas de desarrollo (pylint)
pip install -e ".[dev]"
```

No hay suite de tests automatizados en este proyecto.

## Gotchas críticos de arquitectura

**Doble sys.path — patrón obligatorio en todos los módulos de `src/`:**  
Cada módulo dentro de `src/` hace `sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))` al inicio del archivo para resolver imports entre ellos. Sin esto los imports entre módulos de `src/` fallan cuando se ejecuta desde la raíz. `main.py` tiene una función `_configurar_ruta()` que se llama en el nivel de módulo (antes de los imports), y `reporter.py` lo hace directamente.

**Imports después del sys.path necesitan suprimir advertencias:**  
```python
from comparator import (  # pylint: disable=wrong-import-position
    ...
)
```
El pylint marca estos imports como `wrong-import-position` porque van después de código. Siempre añadir el disable inline.

**lxml requiere suprimir c-extension-no-member en dos niveles:**  
- En el import: `from lxml import etree  # pylint: disable=c-extension-no-member`
- En los `try/except` que usan `etree.fromstring` y `etree.XMLSyntaxError`: `# pylint: disable=c-extension-no-member`

**`_comparar_xml_dom` solo activa el análisis DOM si NO hay diferencias de texto:**  
```python
if not diferencias_existentes and diferencias_dom:
    nuevas_diferencias.extend(diferencias_dom)
```
El diff de texto tiene prioridad. El DOM solo entra en juego cuando el diff de texto no detectó nada (ej: atributos reordenados). No es un fallback sino una segunda pasada condicional.

**`DiferenciaDetalle.opcodes_inline` — campo nuevo con default vacío:**  
Las instancias creadas para casos `AUSENTE_EN_ERP/SAT` no pasan `opcodes_inline`, aprovechando el `field(default_factory=list)`. Si se añaden constructores directos de `DiferenciaDetalle` sin `opcodes_inline`, `_resaltar_inline` simplemente escapa el texto sin marcado, lo cual es correcto.

**Carpetas de datos no se versionan:**  
`erpCFDIs/`, `satCFDIs/` y `reports/` están en `.gitignore`. El programa espera que existan en tiempo de ejecución; si no, lanza `FileNotFoundError` con mensaje descriptivo.

## Restricciones de calidad

- Pylint **10/10** obligatorio — no negociable.
- Máx. línea: **100 caracteres** (`.pylintrc`).
- Máx. argumentos posicionales por función: **7** (`.pylintrc`).
- Todo el código, mensajes de consola, HTML y comentarios en **español (México/Latinoamérica)**.
- Todas las funciones requieren **docstring** + **type hints** completos.
- No variables globales. No lógica en nivel de módulo salvo `_configurar_ruta()` en `main.py`.

## Convenciones de naming

| Elemento | Convención | Ejemplo |
|---|---|---|
| Funciones privadas | `_snake_case` | `_comparar_nodos` |
| Clases | `PascalCase` en español | `ResultadoArchivo`, `EstadoArchivo` |
| Constantes de módulo | `_MAYUSCULAS` o `_PascalCase` | `_CSS`, `_JS` |
| Parámetros | `snake_case` descriptivo en español | `ruta_erp`, `lineas_sat` |

## Estructura de datos clave

`DiferenciaDetalle` (dataclass) — unidad central de información de diferencias:
- `opcodes_inline: List[Tuple]` — precalculado en `comparator.py`, consumido en `reporter.py` para el resaltado HTML inline. Lista vacía = sin resaltado (texto solo escapado).

`ResultadoArchivo` almacena tanto `diferencias` (lista de `DiferenciaDetalle`) como `lineas_erp`/`lineas_sat`/`opcodes_diff` para la vista diff lado a lado. No dupliques lógica entre ambas representaciones.
