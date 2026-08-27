"""
Módulo de generación del reporte HTML para la comparación de CFDIs.

Genera un archivo HTML autocontenido (CSS y JS embebidos) con:
- Resumen ejecutivo con totales.
- Tabla de resultados por archivo.
- Vista diff lado a lado para archivos con diferencias.
- Listado detallado de cada diferencia encontrada.
"""

import html
import os
import sys
from datetime import datetime
from typing import List, Tuple

# Agrega src/ al path para importaciones locales al ejecutar directamente.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from comparator import (  # pylint: disable=wrong-import-position
    DiferenciaDetalle,
    EstadoArchivo,
    ResultadoArchivo,
    ResultadoComparacion,
    calcular_opcodes_inline,
)


def _escapar(texto: str) -> str:
    """
    Escapa caracteres HTML especiales en una cadena de texto.

    Args:
        texto: Texto que puede contener caracteres especiales HTML.

    Returns:
        Texto con caracteres HTML escapados.
    """
    return html.escape(str(texto))


def _resaltar_inline(texto: str, opcodes: List[Tuple], lado: str) -> str:
    """
    Construye HTML con resaltado inline de los fragmentos que difieren.

    Recorre los opcodes a nivel de caracteres producidos por
    ``calcular_opcodes_inline`` y envuelve cada fragmento distinto en un
    ``<span>`` con la clase CSS correspondiente al lado (ERP u SAT), dejando
    el texto coincidente sin clase adicional.

    Si los opcodes están vacíos (cadena vacía, idénticas, o sin contraparte)
    devuelve simplemente el texto escapado sin marcado extra.

    Args:
        texto: Cadena original del lado indicado (ya recortada de saltos de línea).
        opcodes: Lista de tuplas ``(tag, i1, i2, j1, j2)`` de caracteres.
                 Cuando ``lado='erp'`` se usan los índices ``i1:i2``;
                 cuando ``lado='sat'`` se usan ``j1:j2``.
        lado: ``'erp'`` para el fragmento original o ``'sat'`` para el nuevo.

    Returns:
        Cadena HTML con ``<span class="diff-inline-old">`` o
        ``<span class="diff-inline-new">`` alrededor de los fragmentos distintos.
    """
    if not opcodes:
        return _escapar(texto)

    clase_cambio = "diff-inline-old" if lado == "erp" else "diff-inline-new"
    partes: List[str] = []

    for tag, i1, i2, j1, j2 in opcodes:
        inicio = i1 if lado == "erp" else j1
        fin = i2 if lado == "erp" else j2
        fragmento = _escapar(texto[inicio:fin])

        if tag == "equal":
            partes.append(fragmento)
        elif tag in ("replace", "delete") and lado == "erp":
            partes.append(f"<span class='{clase_cambio}'>{fragmento}</span>")
        elif tag in ("replace", "insert") and lado == "sat":
            partes.append(f"<span class='{clase_cambio}'>{fragmento}</span>")
        else:
            # Fragmento del otro lado que no aplica a este: sin contenido visible.
            pass

    return "".join(partes)


def _clase_estado(estado: EstadoArchivo) -> str:
    """
    Retorna la clase CSS correspondiente al estado del archivo.

    Args:
        estado: Estado del archivo comparado.

    Returns:
        Nombre de la clase CSS asociada.
    """
    mapa = {
        EstadoArchivo.IGUAL: "estado-igual",
        EstadoArchivo.DIFERENTE: "estado-diferente",
        EstadoArchivo.AUSENTE_EN_ERP: "estado-ausente",
        EstadoArchivo.AUSENTE_EN_SAT: "estado-ausente",
    }
    return mapa.get(estado, "")


def _etiqueta_estado(estado: EstadoArchivo) -> str:
    """
    Retorna la etiqueta de texto legible para el estado del archivo.

    Args:
        estado: Estado del archivo comparado.

    Returns:
        Texto descriptivo del estado.
    """
    return estado.value


def _fila_diff_igual(
    lineas: List[str], i1: int, i2: int, num_erp: int, num_sat: int
) -> Tuple[List[str], int, int]:
    """
    Genera filas HTML para bloques de líneas iguales en el diff.

    Args:
        lineas: Lista de líneas (ERP, usada en ambos lados por ser igual).
        i1: Índice de inicio del bloque igual.
        i2: Índice de fin del bloque igual.
        num_erp: Contador de línea ERP actual.
        num_sat: Contador de línea SAT actual.

    Returns:
        Tupla con (filas_html, nuevo_num_erp, nuevo_num_sat).
    """
    filas: List[str] = []
    for idx in range(i2 - i1):
        num_erp += 1
        num_sat += 1
        contenido = _escapar(lineas[i1 + idx].rstrip("\n\r"))
        filas.append(
            f"<tr class='igual'>"
            f"<td class='num'>{num_erp}</td>"
            f"<td class='contenido'>{contenido}</td>"
            f"<td class='num'>{num_sat}</td>"
            f"<td class='contenido'>{contenido}</td>"
            f"</tr>"
        )
    return filas, num_erp, num_sat


def _celdas_diff_fila(
    lin_erp_raw: str,
    lin_sat_raw: str,
    num_erp: int,
    num_sat: int,
) -> Tuple[str, str]:
    """
    Construye las dos celdas HTML de una fila de diff con resaltado inline.

    Cuando ambas celdas tienen contenido textual, aplica resaltado a nivel
    de caracteres.  Si sólo una de ellas tiene contenido, devuelve la celda
    vacía con la clase ``vacio`` y la otra sin resaltado inline.

    Args:
        lin_erp_raw: Línea ERP ya recortada de saltos de línea, o ``""`` si ausente.
        lin_sat_raw: Línea SAT ya recortada de saltos de línea, o ``""`` si ausente.
        num_erp: Número de línea ERP para mostrar en la celda (ya incrementado).
        num_sat: Número de línea SAT para mostrar en la celda (ya incrementado).

    Returns:
        Tupla ``(td_erp_html, td_sat_html)`` listas para insertar en la fila.
    """
    ambas_presentes = bool(lin_erp_raw) and bool(lin_sat_raw)

    if lin_erp_raw != "" or lin_sat_raw != "":
        opcodes = calcular_opcodes_inline(lin_erp_raw, lin_sat_raw) if ambas_presentes else []
    else:
        opcodes = []

    if lin_erp_raw != "":
        contenido_erp = _resaltar_inline(lin_erp_raw, opcodes, "erp")
        td_erp = (
            f"<td class='num'>{num_erp}</td>"
            f"<td class='contenido diff-erp'>{contenido_erp}</td>"
        )
    else:
        td_erp = "<td class='num'></td><td class='contenido diff-erp vacio'></td>"

    if lin_sat_raw != "":
        contenido_sat = _resaltar_inline(lin_sat_raw, opcodes, "sat")
        td_sat = (
            f"<td class='num'>{num_sat}</td>"
            f"<td class='contenido diff-sat'>{contenido_sat}</td>"
        )
    else:
        td_sat = "<td class='num'></td><td class='contenido diff-sat vacio'></td>"

    return td_erp, td_sat


def _fila_diff_cambio(
    bloque_erp: List[str],
    bloque_sat: List[str],
    num_erp: int,
    num_sat: int,
    tag: str,
) -> Tuple[List[str], int, int]:
    """
    Genera filas HTML para bloques con cambios (replace, delete, insert).

    Aplica resaltado inline a nivel de caracteres en las filas donde ambos
    lados tienen contenido textual.

    Args:
        bloque_erp: Líneas del ERP en el bloque de cambio.
        bloque_sat: Líneas del SAT en el bloque de cambio.
        num_erp: Contador de línea ERP antes del bloque.
        num_sat: Contador de línea SAT antes del bloque.
        tag: Tipo de cambio: 'replace', 'delete' o 'insert'.

    Returns:
        Tupla con (filas_html, nuevo_num_erp, nuevo_num_sat).
    """
    _ = tag  # El tipo de cambio lo determina la presencia/ausencia de líneas.
    filas: List[str] = []
    max_len = max(len(bloque_erp), len(bloque_sat))

    for idx in range(max_len):
        hay_erp = idx < len(bloque_erp)
        hay_sat = idx < len(bloque_sat)
        lin_erp_raw = bloque_erp[idx].rstrip("\n\r") if hay_erp else ""
        lin_sat_raw = bloque_sat[idx].rstrip("\n\r") if hay_sat else ""

        if hay_erp:
            num_erp += 1
        if hay_sat:
            num_sat += 1

        td_erp, td_sat = _celdas_diff_fila(lin_erp_raw, lin_sat_raw, num_erp, num_sat)
        filas.append(f"<tr class='diferente'>{td_erp}{td_sat}</tr>")

    return filas, num_erp, num_sat


def _generar_diff_html(resultado: ResultadoArchivo) -> str:
    """
    Genera el HTML del diff lado a lado para un archivo con diferencias.

    Args:
        resultado: Resultado de la comparación del archivo.

    Returns:
        Cadena HTML con la vista diff lado a lado.
    """
    if not resultado.lineas_erp and not resultado.lineas_sat:
        return "<p class='aviso'>Sin contenido disponible para mostrar diff.</p>"

    filas_html: List[str] = []
    num_erp = 0
    num_sat = 0

    for tag, i1, i2, j1, j2 in resultado.opcodes_diff:
        if tag == "equal":
            nuevas_filas, num_erp, num_sat = _fila_diff_igual(
                resultado.lineas_erp, i1, i2, num_erp, num_sat
            )
        else:
            bloque_erp = resultado.lineas_erp[i1:i2]
            bloque_sat = resultado.lineas_sat[j1:j2]
            nuevas_filas, num_erp, num_sat = _fila_diff_cambio(
                bloque_erp, bloque_sat, num_erp, num_sat, tag
            )
        filas_html.extend(nuevas_filas)

    filas_str = "\n".join(filas_html)
    return (
        "<div class='diff-container'>"
        "<table class='diff-tabla'>"
        "<thead>"
        "<tr>"
        "<th colspan='2' class='cabecera-erp'>ERP</th>"
        "<th colspan='2' class='cabecera-sat'>SAT</th>"
        "</tr>"
        "<tr>"
        "<th class='col-num'>#</th>"
        "<th class='col-contenido'>Contenido</th>"
        "<th class='col-num'>#</th>"
        "<th class='col-contenido'>Contenido</th>"
        "</tr>"
        "</thead>"
        f"<tbody>{filas_str}</tbody>"
        "</table>"
        "</div>"
    )


def _fila_tabla_diferencia(dif: DiferenciaDetalle) -> str:
    """
    Genera la fila HTML de la tabla de diferencias para una entrada individual.

    Aplica resaltado inline a nivel de caracteres cuando ambos lados tienen
    contenido textual.  Si alguno está vacío o ausente, mantiene el estilo
    de bloque sin resaltado inline.

    Args:
        dif: Objeto con los datos de una diferencia individual.

    Returns:
        Cadena HTML ``<tr>…</tr>`` con la fila completa.
    """
    linea_erp = str(dif.numero_linea_erp) if dif.numero_linea_erp else "—"
    linea_sat = str(dif.numero_linea_sat) if dif.numero_linea_sat else "—"

    # Usar opcodes_inline ya calculados; si están vacíos, _resaltar_inline
    # devuelve el texto escapado sin ningún marcado extra.
    html_erp = _resaltar_inline(dif.contenido_erp, dif.opcodes_inline, "erp")
    html_sat = _resaltar_inline(dif.contenido_sat, dif.opcodes_inline, "sat")

    return (
        f"<tr>"
        f"<td>{linea_erp}</td>"
        f"<td>{linea_sat}</td>"
        f"<td class='diff-erp'>{html_erp}</td>"
        f"<td class='diff-sat'>{html_sat}</td>"
        f"<td>{_escapar(dif.tipo)}</td>"
        f"</tr>"
    )


def _generar_tabla_diferencias(resultado: ResultadoArchivo) -> str:
    """
    Genera la tabla HTML con el listado detallado de diferencias.

    Args:
        resultado: Resultado de la comparación del archivo.

    Returns:
        Cadena HTML con la tabla de diferencias o cadena vacía si no hay.
    """
    if not resultado.diferencias:
        return ""

    filas: List[str] = [_fila_tabla_diferencia(dif) for dif in resultado.diferencias]

    filas_str = "\n".join(filas)
    return (
        "<h4>Listado de diferencias específicas</h4>"
        "<div class='tabla-scroll'>"
        "<table class='tabla-diferencias'>"
        "<thead>"
        "<tr>"
        "<th>Línea ERP</th>"
        "<th>Línea SAT</th>"
        "<th>Contenido ERP</th>"
        "<th>Contenido SAT</th>"
        "<th>Tipo de diferencia</th>"
        "</tr>"
        "</thead>"
        f"<tbody>{filas_str}</tbody>"
        "</table>"
        "</div>"
    )


def _generar_seccion_archivo(resultado: ResultadoArchivo) -> str:
    """
    Genera la sección HTML de detalle para un archivo con diferencias.

    Args:
        resultado: Resultado de la comparación del archivo.

    Returns:
        Cadena HTML con el detalle del archivo y su diff.
    """
    clase = _clase_estado(resultado.estado)
    id_seccion = resultado.nombre_archivo.replace(".", "_").replace("-", "_")
    diff_html = _generar_diff_html(resultado)
    tabla_diferencias = _generar_tabla_diferencias(resultado)

    return (
        f"<div id='{id_seccion}' class='seccion-archivo {clase}'>"
        f"<h3 class='nombre-archivo'>"
        f"<span class='badge {clase}'>{_etiqueta_estado(resultado.estado)}</span>"
        f" {_escapar(resultado.nombre_archivo)}"
        f"</h3>"
        f"<p><strong>Diferencias encontradas:</strong> {resultado.cantidad_diferencias}</p>"
        f"<h4>Vista diff lado a lado</h4>"
        f"{diff_html}"
        f"{tabla_diferencias}"
        f"</div>"
    )


def _generar_tabla_resumen(resultados: List[ResultadoArchivo]) -> str:
    """
    Genera la tabla HTML de resumen con todos los archivos y sus estados.

    Args:
        resultados: Lista de resultados de comparación.

    Returns:
        Cadena HTML con la tabla de resumen.
    """
    filas: List[str] = []
    for resultado in resultados:
        clase = _clase_estado(resultado.estado)
        id_seccion = resultado.nombre_archivo.replace(".", "_").replace("-", "_")
        enlace = ""
        if resultado.estado == EstadoArchivo.DIFERENTE:
            enlace = f'<a href="#{id_seccion}" class="enlace-detalle">Ver detalle ↓</a>'

        filas.append(
            f"<tr class='{clase}'>"
            f"<td>{_escapar(resultado.nombre_archivo)}</td>"
            f"<td><span class='badge {clase}'>{_etiqueta_estado(resultado.estado)}</span></td>"
            f"<td class='centrar'>{resultado.cantidad_diferencias}</td>"
            f"<td class='centrar'>{enlace}</td>"
            f"</tr>"
        )

    filas_str = "\n".join(filas)
    return (
        "<table class='tabla-resumen'>"
        "<thead><tr>"
        "<th>Archivo</th>"
        "<th>Estado</th>"
        "<th>Difs. encontradas</th>"
        "<th>Acciones</th>"
        "</tr></thead>"
        f"<tbody>{filas_str}</tbody>"
        "</table>"
    )


_CSS = """
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: 'Segoe UI', Arial, sans-serif;
      font-size: 13px;
      background: #f4f6f9;
      color: #222;
      line-height: 1.5;
    }
    .encabezado {
      background: #1a3a5c;
      color: #fff;
      padding: 24px 32px;
      border-bottom: 4px solid #2e6da4;
    }
    .encabezado h1 { font-size: 22px; margin-bottom: 8px; }
    .encabezado p  { font-size: 12px; opacity: 0.85; margin: 2px 0; }
    .contenido-principal { max-width: 1200px; margin: 0 auto; padding: 24px 16px; }
    .tarjetas-resumen {
      display: flex; gap: 16px; flex-wrap: wrap; margin-bottom: 28px;
    }
    .tarjeta {
      flex: 1; min-width: 140px; padding: 16px 20px;
      border-radius: 6px; text-align: center;
      border: 1px solid #dde3ea;
      background: #fff;
    }
    .tarjeta .numero { font-size: 32px; font-weight: 700; }
    .tarjeta .etiqueta { font-size: 11px; text-transform: uppercase; color: #666; }
    .tarjeta-total     { border-left: 4px solid #2e6da4; }
    .tarjeta-igual     { border-left: 4px solid #27a145; }
    .tarjeta-diferente { border-left: 4px solid #d9363e; }
    .tarjeta-ausente   { border-left: 4px solid #d97706; }
    h2 { font-size: 16px; margin: 24px 0 12px; color: #1a3a5c;
         border-bottom: 2px solid #dde3ea; padding-bottom: 6px; }
    h3 { font-size: 14px; margin: 0; }
    h4 { font-size: 12px; color: #444; margin: 16px 0 8px;
         text-transform: uppercase; letter-spacing: 0.5px; }
    .tabla-resumen, .tabla-diferencias {
      width: 100%; border-collapse: collapse; background: #fff;
      border: 1px solid #dde3ea; border-radius: 4px; margin-bottom: 16px;
    }
    .tabla-resumen th, .tabla-diferencias th {
      background: #1a3a5c; color: #fff; padding: 8px 12px;
      font-size: 11px; text-align: left; white-space: nowrap;
    }
    .tabla-resumen td, .tabla-diferencias td {
      padding: 6px 12px; border-bottom: 1px solid #eef0f3;
      vertical-align: middle; word-break: break-all;
    }
    .tabla-resumen tr:last-child td { border-bottom: none; }
    .centrar { text-align: center; }
    .enlace-detalle {
      color: #2e6da4; font-size: 11px; text-decoration: none;
    }
    .enlace-detalle:hover { text-decoration: underline; }
    .badge {
      display: inline-block; padding: 2px 8px; border-radius: 12px;
      font-size: 10px; font-weight: 700; text-transform: uppercase;
    }
    .estado-igual     { background: #d1fae5; color: #065f46; }
    .estado-diferente { background: #fee2e2; color: #991b1b; }
    .estado-ausente   { background: #fef3c7; color: #92400e; }
    .seccion-archivo {
      border: 1px solid #dde3ea; border-radius: 6px;
      margin-bottom: 24px; background: #fff; overflow: hidden;
    }
    .nombre-archivo {
      padding: 12px 16px; background: #f7f9fc;
      border-bottom: 1px solid #dde3ea;
      display: flex; align-items: center; gap: 10px;
    }
    .seccion-archivo > p { padding: 8px 16px; color: #555; }
    .seccion-archivo h4  { padding: 0 16px; }
    .diff-container {
      overflow-x: auto; max-height: 480px;
      border-top: 1px solid #dde3ea;
      margin: 8px 0;
    }
    .diff-tabla {
      width: 100%; border-collapse: collapse;
      font-family: 'Courier New', Courier, monospace; font-size: 11px;
    }
    .diff-tabla .cabecera-erp { background: #1e3a5f; color: #fff; text-align: center; }
    .diff-tabla .cabecera-sat { background: #0f5132; color: #fff; text-align: center; }
    .diff-tabla th { padding: 4px 8px; }
    .diff-tabla td { padding: 1px 6px; vertical-align: top; }
    .diff-tabla .col-num { width: 36px; text-align: right; }
    .diff-tabla .num {
      width: 36px; text-align: right; color: #999;
      font-size: 10px; user-select: none; background: #f8f9fa;
    }
    .diff-tabla .contenido { white-space: pre-wrap; word-break: break-all; }
    .diff-tabla tr.igual .contenido { background: #fff; color: #444; }
    .diff-erp { background: #fff0f0; color: #7a0000; }
    .diff-sat { background: #f0fff4; color: #004d00; }
    .diff-inline-old {
        background-color: #ff4d4d;
        color: #000;
        border-radius: 3px;
        padding: 0 2px;
        font-weight: bold;
    }
    .diff-inline-new {
        background-color: #ffd700;
        color: #000;
        border-radius: 3px;
        padding: 0 2px;
        font-weight: bold;
    }
    .vacio    { background: #f0f0f0 !important; }
    .tabla-scroll { overflow-x: auto; padding: 0 16px 16px; }
    .tabla-diferencias td.diff-erp { color: #7a0000; background: #fff0f0; }
    .tabla-diferencias td.diff-sat { color: #004d00; background: #f0fff4; }
    .aviso { padding: 12px; color: #666; font-style: italic; }
    .pie {
      text-align: center; font-size: 11px; color: #999;
      border-top: 1px solid #dde3ea; margin-top: 32px;
      padding: 14px 0 10px;
    }
"""

_JS = """
    document.querySelectorAll('.diff-container').forEach(function(cont) {
      var tabla = cont.querySelector('tbody');
      if (!tabla) return;
      var total = tabla.rows.length;
      if (total > 200) {
        var mostrar = 100;
        for (var i = mostrar; i < total; i++) {
          tabla.rows[i].style.display = 'none';
        }
        var btn = document.createElement('button');
        btn.textContent = 'Mostrar todas las ' + total + ' líneas';
        btn.style.cssText = 'margin:8px 0 4px 16px;padding:4px 12px;cursor:pointer;font-size:11px;';
        btn.addEventListener('click', function() {
          for (var j = 0; j < total; j++) {
            tabla.rows[j].style.display = '';
          }
          btn.remove();
        });
        cont.parentNode.insertBefore(btn, cont);
      }
    });
"""


def _generar_tarjetas(resultado_comparacion: ResultadoComparacion) -> str:
    """
    Genera el HTML de las tarjetas de resumen ejecutivo.

    Args:
        resultado_comparacion: Objeto con los totales de la comparación.

    Returns:
        Cadena HTML con las tarjetas de resumen.
    """
    total_archivos = len(resultado_comparacion.resultados)
    total_iguales = resultado_comparacion.total_iguales
    total_diferentes = resultado_comparacion.total_diferentes
    total_ausentes = (
        resultado_comparacion.total_ausentes_erp
        + resultado_comparacion.total_ausentes_sat
    )
    return (
        "<div class='tarjetas-resumen'>\n"
        f"<div class='tarjeta tarjeta-total'>"
        f"<div class='numero'>{total_archivos}</div>"
        f"<div class='etiqueta'>Total archivos</div></div>\n"
        f"<div class='tarjeta tarjeta-igual'>"
        f"<div class='numero'>{total_iguales}</div>"
        f"<div class='etiqueta'>Iguales</div></div>\n"
        f"<div class='tarjeta tarjeta-diferente'>"
        f"<div class='numero'>{total_diferentes}</div>"
        f"<div class='etiqueta'>Diferentes</div></div>\n"
        f"<div class='tarjeta tarjeta-ausente'>"
        f"<div class='numero'>{total_ausentes}</div>"
        f"<div class='etiqueta'>Ausentes</div></div>\n"
        "</div>"
    )


def _construir_cuerpo_html(
    fecha_legible: str,
    ruta_erp_abs: str,
    ruta_sat_abs: str,
    tarjetas: str,
    tabla_resumen: str,
    secciones_detalle: str,
) -> str:
    """
    Construye el cuerpo HTML completo del reporte.

    Args:
        fecha_legible: Fecha y hora formateada para mostrar.
        ruta_erp_abs: Ruta absoluta a la carpeta ERP.
        ruta_sat_abs: Ruta absoluta a la carpeta SAT.
        tarjetas: HTML de las tarjetas de resumen.
        tabla_resumen: HTML de la tabla de resumen.
        secciones_detalle: HTML del detalle de archivos con diferencias.

    Returns:
        Documento HTML completo como cadena.
    """
    return (
        "<!DOCTYPE html>\n"
        "<html lang='es-MX'>\n"
        "<head>\n"
        "<meta charset='UTF-8' />\n"
        "<meta name='viewport' content='width=device-width, initial-scale=1.0' />\n"
        f"<title>Reporte de Comparación de CFDIs — {fecha_legible}</title>\n"
        f"<style>{_CSS}</style>\n"
        "</head>\n"
        "<body>\n"
        "<header class='encabezado'>\n"
        "<h1>Reporte de Comparación de CFDIs — ERP vs SAT</h1>\n"
        f"<p><strong>Fecha y hora de generación:</strong> {fecha_legible}</p>\n"
        f"<p><strong>Carpeta ERP:</strong> {_escapar(ruta_erp_abs)}</p>\n"
        f"<p><strong>Carpeta SAT:</strong> {_escapar(ruta_sat_abs)}</p>\n"
        "</header>\n"
        "<main class='contenido-principal'>\n"
        "<h2>Resumen ejecutivo</h2>\n"
        f"{tarjetas}\n"
        "<h2>Tabla de resumen por archivo</h2>\n"
        f"{tabla_resumen}\n"
        "<h2>Detalle de archivos con diferencias</h2>\n"
        f"{secciones_detalle}\n"
        "</main>\n"
        "<footer class='pie'>"
        "Reporte generado automáticamente por el Comparador de CFDIs ERP vs SAT"
        "</footer>\n"
        f"<script>{_JS}</script>\n"
        "</body>\n"
        "</html>"
    )


def generar_reporte_html(
    resultado_comparacion: ResultadoComparacion,
    carpeta_reportes: str,
) -> str:
    """
    Genera el archivo HTML del reporte de comparación de CFDIs.

    El HTML es completamente autocontenido: CSS y JS embebidos, sin
    dependencias externas. Puede visualizarse en cualquier navegador.

    Args:
        resultado_comparacion: Objeto con todos los resultados de la comparación.
        carpeta_reportes: Ruta a la carpeta donde se guardará el reporte.

    Returns:
        Ruta absoluta del archivo HTML generado.

    Raises:
        OSError: Si no se puede crear la carpeta o escribir el archivo.
    """
    os.makedirs(carpeta_reportes, exist_ok=True)
    ahora = datetime.now()
    nombre_archivo = f"reporte_comparacion_{ahora.strftime('%Y%m%d_%H%M%S')}.html"
    ruta_salida = os.path.join(carpeta_reportes, nombre_archivo)

    secciones_partes: List[str] = [
        _generar_seccion_archivo(r)
        for r in resultado_comparacion.resultados
        if r.estado == EstadoArchivo.DIFERENTE
    ]
    secciones_detalle = "\n".join(secciones_partes) or (
        "<p class='aviso'>No se encontraron archivos con diferencias.</p>"
    )

    contenido_html = _construir_cuerpo_html(
        fecha_legible=ahora.strftime("%d/%m/%Y %H:%M:%S"),
        ruta_erp_abs=os.path.abspath(resultado_comparacion.ruta_erp),
        ruta_sat_abs=os.path.abspath(resultado_comparacion.ruta_sat),
        tarjetas=_generar_tarjetas(resultado_comparacion),
        tabla_resumen=_generar_tabla_resumen(resultado_comparacion.resultados),
        secciones_detalle=secciones_detalle,
    )

    with open(ruta_salida, "w", encoding="utf-8") as archivo_salida:
        archivo_salida.write(contenido_html)

    return os.path.abspath(ruta_salida)
