"""
Punto de entrada del Comparador de CFDIs ERP vs SAT.

Ejecutar con:
    python src/main.py

Compara exhaustivamente los archivos XML (CFDIs del SAT México) ubicados
en las carpetas erpCFDIs y satCFDIs, y genera un reporte HTML detallado
en la carpeta reports/.
"""

import os
import sys


def _configurar_ruta() -> None:
    """
    Agrega el directorio src/ al path de Python para importaciones locales.

    Permite ejecutar el programa directamente con `python src/main.py`
    sin necesidad de instalar el paquete.
    """
    directorio_src = os.path.dirname(os.path.abspath(__file__))
    if directorio_src not in sys.path:
        sys.path.insert(0, directorio_src)


_configurar_ruta()

# pylint: disable=wrong-import-position,import-error
from comparator import comparar_carpetas  # noqa: E402
from reporter import generar_reporte_html  # noqa: E402


def main() -> None:
    """
    Función principal del comparador de CFDIs.

    Determina las rutas de las carpetas, ejecuta la comparación exhaustiva
    y genera el reporte HTML en la carpeta reports/.

    Maneja errores descriptivos en caso de que las carpetas no existan
    o estén vacías, evitando generar reportes vacíos sin sentido.
    """
    # Detectar la raíz del proyecto (un nivel arriba de src/)
    directorio_src = os.path.dirname(os.path.abspath(__file__))
    raiz_proyecto = os.path.dirname(directorio_src)

    ruta_erp = os.path.join(raiz_proyecto, "erpCFDIs")
    ruta_sat = os.path.join(raiz_proyecto, "satCFDIs")
    ruta_reportes = os.path.join(raiz_proyecto, "reports")

    try:
        resultado = comparar_carpetas(ruta_erp, ruta_sat)
    except FileNotFoundError as exc:
        print(f"\n[ERROR] Carpeta no encontrada: {exc}")
        print(
            "Verifique que las carpetas 'erpCFDIs' y 'satCFDIs' existan "
            "en el directorio raíz del proyecto."
        )
        sys.exit(1)
    except ValueError as exc:
        print(f"\n[ERROR] Sin archivos para comparar: {exc}")
        sys.exit(1)

    if not resultado.resultados:
        print(
            "\n[AVISO] No se encontraron archivos XML en las carpetas indicadas. "
            "No se generará reporte."
        )
        sys.exit(0)

    try:
        ruta_reporte = generar_reporte_html(resultado, ruta_reportes)
        print("✔  Reporte HTML generado exitosamente:")
        print(f"   {ruta_reporte}\n")
    except OSError as exc:
        print(f"\n[ERROR] No se pudo guardar el reporte HTML: {exc}")
        sys.exit(1)


if __name__ == "__main__":
    main()
