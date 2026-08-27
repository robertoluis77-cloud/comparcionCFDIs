# 🧾 Comparador de CFDIs — ERP vs SAT

[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[![Pylint 10/10](https://img.shields.io/badge/pylint-10%2F10-brightgreen)](https://pylint.readthedocs.io/)
[![Licencia MIT](https://img.shields.io/badge/licencia-MIT-green)](LICENSE)

Herramienta de línea de comandos en Python que compara exhaustivamente archivos XML de **CFDI (Comprobante Fiscal Digital por Internet)** entre dos fuentes:

- 📂 **`erpCFDIs/`** — XMLs exportados desde tu sistema ERP
- 📂 **`satCFDIs/`** — XMLs descargados directamente del SAT

Al finalizar, genera un **reporte HTML autocontenido** con resaltado visual para que puedas identificar de un vistazo qué archivos son idénticos, cuáles difieren y exactamente **qué caracteres cambiaron** en cada diferencia.

---

## ✨ Características principales

- 🔍 **Comparación dual**: diff línea por línea *y* análisis del árbol DOM XML, para detectar tanto diferencias tipográficas como semánticas.
- 🎨 **Resaltado inline a nivel de caracteres**: dentro de una línea diferente, sólo los fragmentos exactos que cambiaron se pintan en rojo (ERP) o amarillo (SAT). El resto del texto permanece con color base.
- 📊 **Reporte HTML autocontenido**: CSS y JS embebidos, sin dependencias externas. Se abre directamente en cualquier navegador.
- 📋 **Vista diff lado a lado**: tabla ERP | SAT con numeración de líneas.
- ⚡ **Progreso en tiempo real**: la consola muestra `✔ IGUAL`, `✘ DIFERENTE` o `⚠ AUSENTE` archivo por archivo mientras avanza.
- 🔐 **Solo lectura**: el programa **nunca modifica** los archivos XML originales.
- 🌐 **Codificaciones soportadas**: UTF-8, UTF-8 con BOM e ISO-8859-1 (común en CFDIs legacy).

---

## 📋 Requisitos previos

| Requisito | Versión mínima |
|-----------|----------------|
| Python    | 3.9            |
| lxml      | 5.3.0          |

> No se requiere ninguna dependencia del sistema operativo además de Python.

---

## 🚀 Instalación

### 1. Clonar el repositorio

```bash
git clone https://github.com/tu-usuario/comparador-cfdis.git
cd comparador-cfdis
```

### 2. Crear y activar un entorno virtual

```bash
# Crear el entorno
python -m venv venv

# Activar — Linux / macOS
source venv/bin/activate

# Activar — Windows (PowerShell)
venv\Scripts\Activate.ps1

# Activar — Windows (CMD)
venv\Scripts\activate.bat
```

### 3. Instalar el proyecto

```bash
pip install -e .
```

Para incluir también las dependencias de desarrollo (Pylint, etc.):

```bash
pip install -e ".[dev]"
```

---

## 📁 Preparar los archivos XML

Coloca los archivos XML de CFDI en las carpetas correspondientes antes de ejecutar el programa:

```
comparador-cfdis/
├── erpCFDIs/          ← XMLs exportados desde tu ERP
│   ├── uuid-001.xml
│   ├── uuid-002.xml
│   └── ...
└── satCFDIs/          ← XMLs descargados del portal SAT
    ├── uuid-001.xml
    ├── uuid-002.xml
    └── ...
```

> **Emparejamiento por nombre de archivo**: el programa compara `erpCFDIs/uuid-001.xml` contra `satCFDIs/uuid-001.xml`. Asegúrate de que los nombres coincidan exactamente (incluyendo mayúsculas/minúsculas).

---

## ▶️ Uso

Desde la raíz del proyecto, ejecuta:

```bash
python src/main.py
```

### Ejemplo de salida en consola

```
============================================================
  Comparador de CFDIs — ERP vs SAT
============================================================
  Carpeta ERP : /ruta/al/proyecto/erpCFDIs
  Carpeta SAT : /ruta/al/proyecto/satCFDIs
  Archivos ERP: 16
  Archivos SAT: 16
  Total a procesar: 16
============================================================

[1/16] Comparando: 4e45154c-49c0-423f-a0cf-7f40e9237008.xml
  ✔  IGUAL
[2/16] Comparando: 4e45154c-49c0-423f-a0cf-7f40e9237009.xml
  ✔  IGUAL
...
[14/16] Comparando: 4e45154c-49c0-423f-a0cf-7f40e9237021.xml
  ✘  DIFERENTE (1 diferencia(s))
     → Línea ERP=6 / SAT=6 | Tipo=modificación | ERP: '...Cantidad="5000...' | SAT: '...Cantidad="15000...'

============================================================
  RESUMEN FINAL
============================================================
  ✔  Iguales          : 13
  ✘  Diferentes       : 3
  ⚠  Ausentes en ERP : 0
  ⚠  Ausentes en SAT : 0
============================================================

✔  Reporte HTML generado exitosamente:
   /ruta/al/proyecto/reports/reporte_comparacion_20260827_095203.html
```

### Reporte HTML generado

El archivo se guarda automáticamente en `reports/` con nombre `reporte_comparacion_YYYYMMDD_HHMMSS.html`. Contiene:

1. **Tarjetas de resumen** con totales de archivos iguales, diferentes y ausentes.
2. **Tabla de todos los archivos** con su estado y enlace al detalle.
3. **Sección de detalle por archivo** con:
   - Vista diff lado a lado (ERP en rojo, SAT en verde).
   - Fragmentos exactos que cambiaron resaltados en **rojo intenso** (eliminado) y **amarillo** (nuevo).
   - Tabla de diferencias específicas con número de línea, contenido ERP, contenido SAT y tipo de cambio.

---

## 🗂️ Estructura del proyecto

```
comparador-cfdis/
│
├── erpCFDIs/               # XMLs del ERP (tú los agregas, no se versionan)
├── satCFDIs/               # XMLs del SAT (tú los agregas, no se versionan)
├── reports/                # Reportes HTML generados (no se versionan)
│
├── src/
│   ├── __init__.py         # Marca src/ como paquete Python
│   ├── comparator.py       # Lógica de comparación: diff de texto + análisis DOM XML
│   ├── reporter.py         # Generación del reporte HTML autocontenido
│   └── main.py             # Punto de entrada — ejecutar con: python src/main.py
│
├── .gitignore
├── .pylintrc               # Configuración de Pylint (score 10/10)
├── LICENSE
├── README.md
└── pyproject.toml          # Metadatos del proyecto y dependencias (PEP 517/518)
```

---

## ⚙️ Cómo funciona internamente

```
python src/main.py
       │
       ▼
comparar_carpetas()          ← comparator.py
  ├─ _leer_archivo()         ← detecta encoding (UTF-8 / ISO-8859-1)
  ├─ _comparar_texto()       ← difflib línea por línea
  ├─ _comparar_xml_dom()     ← lxml: diferencias semánticas en atributos/nodos
  └─ calcular_opcodes_inline() ← difflib char-by-char para resaltado inline
       │
       ▼
generar_reporte_html()       ← reporter.py
  ├─ _resaltar_inline()      ← aplica <span> sobre fragmentos distintos
  ├─ _generar_diff_html()    ← tabla lado a lado
  └─ _construir_cuerpo_html() ← HTML final autocontenido
```

---

## 🤝 Contribuciones

¡Las contribuciones son bienvenidas! Sigue estos pasos:

1. Haz un **fork** del repositorio.
2. Crea una rama para tu cambio:
   ```bash
   git checkout -b feature/mi-nueva-funcionalidad
   ```
3. Realiza tus cambios y asegúrate de que Pylint siga en **10/10**:
   ```bash
   python -m pylint src/comparator.py src/reporter.py src/main.py \
     --init-hook="import sys; sys.path.insert(0,'src')"
   ```
4. Haz commit con un mensaje descriptivo:
   ```bash
   git commit -m "feat: descripción clara del cambio"
   ```
5. Abre un **Pull Request** contra la rama `main` con una descripción de qué resuelve o mejora tu cambio.

### Lineamientos de código

- Todas las funciones deben tener **docstring** completo.
- Usar **type hints** en todas las firmas.
- Seguir **PEP 8** estrictamente.
- El score de Pylint debe mantenerse en **10/10**.

---

## 📄 Licencia

Este proyecto está bajo la licencia [MIT](LICENSE). Consulta el archivo `LICENSE` para más detalles.
